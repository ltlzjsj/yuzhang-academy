"""PyMuPDF-based PDF text extraction with header/footer filtering and text cleaning."""
from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from app.services.parser_types import PageText


# Reference section header must be a standalone line (after trimming).
_REF_SECTION = re.compile(
    r"^[ \t]*(?:参\s*考\s*文\s*献|References|REFERENCES|参考书目|引用文献)[ \t]*$",
    re.MULTILINE,
)
# Matches a run of single chars (CJK / ASCII letter / digit / common punct) each
# separated by exactly one ASCII space — i.e. per-char tracking artefacts.
_SPACED_CHARS = re.compile(
    r"(?<!\S)([\u4e00-\u9fff\w.,\-/:])(?: ([\u4e00-\u9fff\w.,\-/:])){2,}(?!\S)"
)
# A line is likely a reference entry if it contains a CN academic reference-type tag
_REF_ENTRY_TAG = re.compile(r"\[\s*[JMCDNSRPZG]\s*\]")
# Sentence-ending punctuation — presence at the end of a line signals a real break
_SENT_END_CHARS = set("。！？.!?；;：:")
# Paragraph/heading starts we want to preserve as line breaks
_PARA_START = re.compile(
    r"^("
    r"[\d一二三四五六七八九十]+[、．.）)]\s"           # 1、 1. 一、
    r"|第[一二三四五六七八九十\d]+[章节部篇]"            # 第3章
    r"|图\s*\d|表\s*\d|公式\s*\d"                     # 图1 表1
    r"|摘\s*要|关键词|Abstract|Keywords"
    r"|[①②③④⑤⑥⑦⑧⑨⑩]"                           # ①②③
    r"|[（(]\s*\d+\s*[）)]\s"                       # (1) （1）
    r")"
)


def parse_pdf(path: str | Path) -> tuple[list[PageText], int]:
    """Extract per-page text with header/footer stripping and reference cut-off."""
    doc = fitz.open(str(path))
    try:
        # Phase 1 — find the first page whose text contains a reference-section marker.
        ref_start_page = _find_reference_start(doc)

        pages: list[PageText] = []
        for i, page in enumerate(doc, start=1):
            # Pages after the references section → blank
            if ref_start_page and i > ref_start_page:
                pages.append(PageText(page=i, text="", char_count=0))
                continue

            raw = _extract_page_text(page)

            # If reference section starts on this page, cut it off
            if ref_start_page == i:
                m = _REF_SECTION.search(raw)
                if m:
                    raw = raw[: m.start()]

            text = _clean_page_text(raw)

            # Also drop any trailing reference-dense tail (defense in depth —
            # catches cases where "参考文献" header was removed by margin clip)
            text = _strip_trailing_references(text)

            pages.append(PageText(page=i, text=text, char_count=len(text)))
        return pages, doc.page_count
    finally:
        doc.close()


def _find_reference_start(doc: "fitz.Document") -> int | None:
    """Return the 1-indexed page where reference section starts, or None."""
    for i, page in enumerate(doc, start=1):
        raw = page.get_text("text") or ""
        if _REF_SECTION.search(raw):
            return i
    return None


def _extract_page_text(page: "fitz.Page") -> str:
    """Return page text minus header/footer zones, preserving paragraph structure."""
    h = page.rect.height
    margin_top = h * 0.07
    margin_bot = h * 0.93

    blocks = page.get_text("blocks", sort=True)
    kept_blocks: list[str] = []
    for blk in blocks:
        x0, y0, x1, y1, txt, _bno, btype = blk
        if btype != 0:  # skip image blocks
            continue
        if y1 <= margin_top or y0 >= margin_bot:  # header / footer
            continue
        t = (txt or "").strip()
        if t:
            kept_blocks.append(t)
    # Blocks become paragraphs — separate with blank line
    return "\n\n".join(kept_blocks)


def _clean_page_text(text: str) -> str:
    """Normalise chars + rejoin wrapped lines into real paragraphs."""
    text = text.replace("\r\n", "\n").replace("\xad", "")

    # --- Normalize spaced-out characters ---
    # "2 0 1 2 年" → "2012年", "地 质 学 报" → "地质学报", "J O U R N A L" → "JOURNAL"
    for _ in range(3):
        text = re.sub(r"([\u4e00-\u9fff\d]) ([\u4e00-\u9fff\d])", r"\1\2", text)
        text = re.sub(r"([A-Z]) ([A-Z])", r"\1\2", text)

    # --- Normalize bracketed reference numbers: "[ 1 6 ]" / "[1, 2]" → "[16]" / "[1,2]" ---
    text = re.sub(
        r"\[\s*(\d[\d\s,，－-]*\d|\d)\s*\]",
        lambda m: "[" + re.sub(r"[\s，]+", ",", m.group(1)).strip(",") + "]",
        text,
    )

    # --- Rejoin ASCII hyphenated words broken at line end ---
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)

    # --- Join column-wrapped lines within a paragraph ---
    paragraphs_out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        joined = _join_wrapped_lines(para)
        if joined:
            paragraphs_out.append(joined)

    return "\n\n".join(paragraphs_out).strip()


def _join_wrapped_lines(paragraph: str) -> str:
    """Inside one paragraph, merge hard-wrapped lines that continue a sentence."""
    lines = [ln.strip() for ln in paragraph.split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""

    # Drop lone page numbers / decorations
    lines = [ln for ln in lines if not (len(ln) <= 4 and re.fullmatch(r"[\d\s·•]+", ln))]
    if not lines:
        return ""

    out: list[str] = []
    buf = ""
    for line in lines:
        if not buf:
            buf = line
            continue
        prev_ends_sentence = buf[-1] in _SENT_END_CHARS
        line_starts_new = bool(_PARA_START.match(line))
        if prev_ends_sentence or line_starts_new:
            out.append(buf)
            buf = line
        else:
            # ASCII alpha boundary gets a space; Chinese joins directly
            if buf[-1].isascii() and buf[-1].isalpha() and line[0].isascii() and line[0].isalpha():
                buf += " " + line
            else:
                buf += line
    if buf:
        out.append(buf)
    return "\n".join(out)


def _strip_trailing_references(text: str) -> str:
    """Drop trailing paragraphs that look like reference entries (heavy [J]/[M]/[C] tags)."""
    paras = text.split("\n\n")
    # Walk from the end and keep chopping while a paragraph is dominated by ref-entry tags
    cutoff = len(paras)
    for idx in range(len(paras) - 1, -1, -1):
        p = paras[idx]
        tags = _REF_ENTRY_TAG.findall(p)
        # Heuristic: 2+ citation-type tags per paragraph = reference entry
        if len(tags) >= 2:
            cutoff = idx
            continue
        break
    return "\n\n".join(paras[:cutoff]).strip()


def is_probably_scanned(pages: list[PageText], threshold: int = 30) -> bool:
    if not pages:
        return False
    sparse = sum(1 for p in pages if p.char_count < threshold)
    return sparse / len(pages) > 0.6
