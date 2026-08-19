"""MinerU-backed PDF parser.

Wraps `mineru.cli.common.do_parse` and converts the produced
`*_content_list.json` into our shared (ParsedBlock, PageText) structure.

Why MinerU:
- Layout-aware extraction (PaddleOCR + DocLayout YOLO) — no letter-spacing
  artefacts, no mid-sentence hard wraps, clean header/footer removal.
- Emits per-block bbox (normalized 0-1000) → we persist to chunks.bbox so
  the frontend can later draw citation popovers.

`do_parse` writes to disk; we read and discard the temp dir on demand.
The heavy model load happens once per process (MinerU caches singletons),
so call sites should be reused (e.g. inside a Celery worker).
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Iterable

from app.core.config import settings
from app.services.parser_types import BlockType, ParsedBlock, PageText
from app.services.text_quality import is_noise_block, strip_latex_islands

log = logging.getLogger(__name__)

# MinerU type strings → our unified BlockType
_TYPE_MAP: dict[str, BlockType] = {
    "text": "text",
    "title": "title",
    "table": "table",
    "image": "figure",
    "equation": "formula",
    "interline_equation": "formula",
    "inline_equation": "formula",
}

# Block types we drop outright (header/footer/page-number already removed by MinerU,
# but keep a defensive filter in case new types appear).
_DROP_TYPES: set[str] = {
    "header",
    "footer",
    "page_footnote",
    "page_number",
    "discarded",
}

# Chinese + English reference-section title patterns (checked on title blocks only).
_REF_TITLES = (
    "参考文献",
    "参 考 文 献",
    "references",
    "reference",
    "参考书目",
    "引用文献",
)


def parse_with_mineru(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
) -> tuple[list[PageText], int]:
    """Run MinerU pipeline on `pdf_path`; return (pages, total_page_count).

    Raises on any failure — caller (dispatcher) handles fallback.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)

    out_root = Path(output_dir or settings.mineru_output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    # Encourage local connections to bypass proxy when the worker inherits one
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1,hf-mirror.com")
    if settings.hf_endpoint.strip():
        os.environ["HF_ENDPOINT"] = settings.hf_endpoint
    else:
        os.environ.pop("HF_ENDPOINT", None)
    if settings.hf_home.strip():
        os.environ["HF_HOME"] = settings.hf_home
    os.environ["MINERU_MODEL_SOURCE"] = settings.mineru_model_source

    # Imported lazily so the rest of the system still boots if MinerU is missing
    from mineru.cli.common import do_parse, read_fn

    stem = pdf_path.stem
    log.info("MinerU: parsing %s → %s (backend=%s)", pdf_path.name, out_root, settings.mineru_backend)
    pdf_bytes = read_fn(pdf_path)

    do_parse(
        output_dir=str(out_root),
        pdf_file_names=[stem],
        pdf_bytes_list=[pdf_bytes],
        p_lang_list=[settings.mineru_lang],
        backend=settings.mineru_backend,
        parse_method=settings.mineru_parse_method,
        formula_enable=True,
        table_enable=True,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=False,
        f_dump_middle_json=False,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=True,
        f_make_md_mode="mm_markdown",
    )

    # parse_method subdir is "auto" | "ocr" | "txt"
    method_dir = settings.mineru_parse_method
    cl_path = out_root / stem / method_dir / f"{stem}_content_list.json"
    if not cl_path.exists():
        # Fallback search (some MinerU builds flatten the path)
        hits = list(out_root.rglob(f"{stem}_content_list.json"))
        if not hits:
            raise FileNotFoundError(f"MinerU produced no content_list.json for {stem}")
        cl_path = hits[0]

    raw_blocks = json.loads(cl_path.read_text(encoding="utf-8"))
    total_pages, pages = _blocks_to_pages(raw_blocks)
    return pages, total_pages


def _find_content_list(stem: str, output_dir: str | Path | None = None) -> Path | None:
    """Locate the MinerU ``*_content_list.json`` for a parsed PDF stem."""
    out_root = Path(output_dir or settings.mineru_output_dir)
    method_dir = settings.mineru_parse_method
    cand = out_root / stem / method_dir / f"{stem}_content_list.json"
    if cand.exists():
        return cand
    hits = list(out_root.rglob(f"{stem}_content_list.json"))
    return hits[0] if hits else None


def ensure_mineru_content_list(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
) -> Path | None:
    """Return MinerU content_list for ``pdf_path``, running MinerU if missing."""
    pdf_path = Path(pdf_path)
    cl_path = _find_content_list(pdf_path.stem, output_dir)
    if cl_path is not None:
        return cl_path
    parse_with_mineru(pdf_path, output_dir)
    return _find_content_list(pdf_path.stem, output_dir)


def collect_page_images(
    pdf_or_stem: str | Path,
    output_dir: str | Path | None = None,
    *,
    ensure: bool = False,
) -> dict[int, list[dict]]:
    """Map 1-based page → list of ``{"img_path", "caption", "src"}`` for a parsed PDF.

    Reads the raw ``content_list.json`` so we capture *every* figure on a page
    (including bare, caption-less ones), which the sentence-based chunker drops.
    ``src`` is the web path under the static mount: ``<stem>/<method>/<img_path>``.
    """
    maybe_path = Path(pdf_or_stem)
    pdf_path = maybe_path if maybe_path.suffix.lower() == ".pdf" else None
    stem = pdf_path.stem if pdf_path is not None else str(pdf_or_stem)

    cl_path = _find_content_list(stem, output_dir)
    if cl_path is None and ensure and pdf_path is not None and pdf_path.exists():
        try:
            cl_path = ensure_mineru_content_list(pdf_path, output_dir)
        except Exception as e:
            log.warning("collect_page_images: MinerU image extraction failed for %s: %s", pdf_path, e)
            return {}
    if cl_path is None:
        return {}
    try:
        raw = json.loads(cl_path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("collect_page_images: failed reading %s: %s", cl_path, e)
        return {}

    method_dir = cl_path.parent.name  # actual method subdir ("auto"/"ocr"/"txt")
    by_page: dict[int, list[dict]] = {}
    seen: set[str] = set()
    for b in raw:
        if (b.get("type") or "").lower() not in ("image", "chart"):
            continue
        img_path = (b.get("img_path") or "").strip()
        if not img_path or img_path in seen:
            continue
        if not (cl_path.parent / img_path).exists():
            log.warning("collect_page_images: missing image file %s under %s", img_path, cl_path.parent)
            continue
        seen.add(img_path)
        page_1idx = int(b.get("page_idx", 0)) + 1
        caption = _join_list(b.get("image_caption") or b.get("chart_caption"))
        by_page.setdefault(page_1idx, []).append(
            {
                "img_path": img_path,
                "caption": caption,
                "src": f"{stem}/{method_dir}/{img_path}".replace("\\", "/"),
            }
        )
    return by_page


def _blocks_to_pages(raw_blocks: list[dict]) -> tuple[int, list[PageText]]:
    """Convert MinerU content_list entries → per-page PageText with ParsedBlock list."""
    # Pass 1 — build ParsedBlock list, respecting reference cut-off
    parsed: list[ParsedBlock] = []
    ref_cutoff_idx: int | None = None

    for i, b in enumerate(raw_blocks):
        mtype = (b.get("type") or "").lower()
        if mtype in _DROP_TYPES:
            continue

        page_idx = int(b.get("page_idx", 0))
        page_1idx = page_idx + 1
        bbox = _coerce_bbox(b.get("bbox"))

        if mtype == "text":
            txt = _clean_text(b.get("text") or "")
            if not txt:
                continue
            level = b.get("text_level")
            # MinerU marks titles as text blocks with text_level set (1–6)
            if level:
                if _is_ref_title(txt):
                    ref_cutoff_idx = i
                    break
                parsed.append(
                    ParsedBlock(
                        page=page_1idx,
                        block_type="title",
                        text=txt,
                        bbox=bbox,
                        level=int(level),
                    )
                )
            else:
                # Strip stray LaTeX debris that leaked outside proper `$...$` spans,
                # then drop the whole block if it's still too digit/formula heavy.
                cleaned = strip_latex_islands(txt)
                if is_noise_block(cleaned):
                    log.debug(
                        "drop noise text block on page %d: %r", page_1idx, cleaned[:60]
                    )
                    continue
                parsed.append(
                    ParsedBlock(page=page_1idx, block_type="text", text=cleaned, bbox=bbox)
                )
            continue

        if mtype == "list":
            items = b.get("list_items") or []
            # list_items is typically a list of strings (or dicts with "text")
            parts: list[str] = []
            for it in items:
                if isinstance(it, str):
                    parts.append(it.strip())
                elif isinstance(it, dict):
                    parts.append(_clean_text(it.get("text") or ""))
            parts = [p for p in parts if p]
            if not parts:
                continue
            parsed.append(
                ParsedBlock(
                    page=page_1idx,
                    block_type="text",
                    text="\n".join(parts),
                    bbox=bbox,
                    extras={"sub_type": b.get("sub_type")},
                )
            )
            continue

        if mtype == "table":
            # Tables are kept out of the retrieval text on purpose — flattened
            # HTML rows become rows of meaningless numbers + LaTeX fragments
            # that wreck embedding quality. We retain caption + footnote for
            # semantic recall, and stash the raw HTML in extras for M5's
            # structured-table retrieval.
            body = b.get("table_body") or ""
            caption = _join_list(b.get("table_caption"))
            footnote = _join_list(b.get("table_footnote"))
            table_text = _table_html_to_text(body)
            txt_parts = [x for x in (caption, table_text, footnote) if x]
            if not txt_parts:
                continue
            parsed.append(
                ParsedBlock(
                    page=page_1idx,
                    block_type="table",
                    text="\n".join(txt_parts),
                    bbox=bbox,
                    extras={
                        "table_html": body,
                        "table_text": table_text,
                        "caption": caption,
                        "footnote": footnote,
                    },
                )
            )
            continue

        if mtype in ("image", "chart"):
            caption = _join_list(b.get("image_caption") or b.get("chart_caption"))
            footnote = _join_list(b.get("image_footnote") or b.get("chart_footnote"))
            # Charts/images may also carry recognised content (HTML/markdown/OCR text).
            inner = _strip_html(
                b.get("content")
                or b.get("image_body")
                or b.get("ocr_text")
                or b.get("text")
                or ""
            )
            txt = "\n".join(x for x in (caption, inner, footnote) if x)
            if not txt:
                continue  # bare figure — skip (not retrievable)
            parsed.append(
                ParsedBlock(
                    page=page_1idx,
                    block_type="figure_caption" if mtype == "image" else "table",
                    text=txt,
                    bbox=bbox,
                    extras={"img_path": b.get("img_path"), "orig_type": mtype},
                )
            )
            continue

        if mtype in ("equation", "interline_equation", "inline_equation"):
            latex = (b.get("text") or "").strip()
            if not latex:
                continue
            parsed.append(
                ParsedBlock(
                    page=page_1idx,
                    block_type="formula",
                    text="[公式]",
                    bbox=bbox,
                    extras={"latex": latex},
                )
            )
            continue

        # Unknown type — be forgiving: keep if it has text
        txt = _clean_text(b.get("text") or "")
        if txt:
            parsed.append(
                ParsedBlock(
                    page=page_1idx,
                    block_type="other",
                    text=txt,
                    bbox=bbox,
                    extras={"orig_type": mtype},
                )
            )

    # Pass 2 — infer total page count
    if raw_blocks:
        max_page_idx = max(int(b.get("page_idx", 0)) for b in raw_blocks)
        total_pages = max_page_idx + 1
    else:
        total_pages = 0

    # Pass 3 — aggregate per page
    by_page: dict[int, list[ParsedBlock]] = {}
    for pb in parsed:
        by_page.setdefault(pb.page, []).append(pb)

    pages: list[PageText] = []
    for p in range(1, total_pages + 1):
        blocks = by_page.get(p, [])
        # Paragraph-like join: block texts separated by a blank line
        text = "\n\n".join(b.text for b in blocks if b.text).strip()
        pages.append(
            PageText(page=p, text=text, char_count=len(text), blocks=blocks)
        )
    return total_pages, pages


# ---------- small utilities ----------


def _coerce_bbox(raw) -> tuple[float, float, float, float]:
    if not raw or not isinstance(raw, (list, tuple)) or len(raw) < 4:
        return (0.0, 0.0, 0.0, 0.0)
    try:
        return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0, 0.0)


def _clean_text(s: str) -> str:
    return (s or "").replace("\u00ad", "").strip()


def _is_ref_title(t: str) -> bool:
    norm = t.strip().lower().replace(" ", "")
    return any(k.replace(" ", "") in norm for k in _REF_TITLES)


def _join_list(v) -> str:
    if not v:
        return ""
    if isinstance(v, list):
        return " ".join(str(x).strip() for x in v if x)
    return str(v).strip()


def _strip_html(html: str) -> str:
    """Minimal HTML→text: collapse tags, keep cell contents space-separated."""
    if not html:
        return ""
    # Replace closing cell/row tags with whitespace so content doesn't collide
    html = re.sub(r"</\s*(td|th)\s*>", " ", html, flags=re.I)
    html = re.sub(r"</\s*tr\s*>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{2,}", "\n", html)
    return html.strip()


def _table_html_to_text(html: str, *, max_rows: int = 18, max_chars: int = 1400) -> str:
    """Convert simple MinerU table HTML into compact row text for retrieval."""
    if not html:
        return ""
    import html as _html

    rows = re.split(r"</\s*tr\s*>", html, flags=re.I)
    out: list[str] = []
    for row in rows:
        cells = re.sub(r"</\s*(td|th)\s*>", "\t", row, flags=re.I)
        cells = re.sub(r"<[^>]+>", "", cells)
        cells = _html.unescape(cells)
        cells = re.sub(r"[ \t\u00a0]+", " ", cells.replace("\r", " ").replace("\n", " "))
        parts = [c.strip() for c in cells.split("\t") if c.strip()]
        if not parts:
            continue
        out.append(" | ".join(parts))
        if len(out) >= max_rows:
            out.append("...")
            break
    text = "\n".join(out).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    if text and not re.search(r"[\u4e00-\u9fffA-Za-z]", text):
        return ""
    return text
