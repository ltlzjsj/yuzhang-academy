"""Chinese-aware chunking over per-block parser output.

Strategy:
- Input: either `list[PageText]` (legacy path — blocks may be empty) or
  `list[ParsedBlock]` (new MinerU path).
- Split each block's text into sentences on CJK + ASCII sentence punctuation.
- Greedily pack sentences into chunks ≤ chunk_size characters.
- Preserve block boundaries by separating with a blank line in the final text —
  frontend's `whitespace-pre-wrap` renders that as a paragraph break.
- Track which blocks a chunk spans to emit per-page bounding-box ranges
  (for PDF-citation popovers in M4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.parser_types import ParsedBlock, PageText
from app.services.text_quality import is_noise_block

_SENT_SPLIT_RE = re.compile(r"(?<=[。！？!?])\s+|(?<=[。！？!?])(?=\S)|\n{2,}")
_SOFT_BREAK_RE = re.compile(r"([，,；;、])")
_MAX_SENTENCE_CHARS = 360


@dataclass
class ChunkPiece:
    seq: int
    text: str
    page: int  # first block's page
    char_count: int
    page_end: int | None = None  # last block's page, if chunk spans pages
    block_types: list[str] = field(default_factory=list)
    bbox_ranges: list[dict] = field(default_factory=list)  # [{"page": n, "bbox": [...]}]
    # Structured artefacts sourced from ParsedBlock.extras, kept alongside the
    # plain-text chunk so the LLM can see full table bodies / formula LaTeX
    # when that block gets retrieved. Each entry is one structured block:
    #   tables:   [{"caption": str, "html": str, "page": int}, ...]
    #   formulas: [{"latex": str, "page": int}, ...]
    tables: list[dict] = field(default_factory=list)
    formulas: list[dict] = field(default_factory=list)


# Internal record: (page, block_idx, block_type, bbox, sentence_text)
_Sent = tuple[int, int, str, tuple[float, float, float, float], str]


def _split_long_sentence(text: str, max_chars: int = _MAX_SENTENCE_CHARS) -> list[str]:
    """Split very long sentence-like spans without losing punctuation."""
    if len(text) <= max_chars:
        return [text]

    parts = _SOFT_BREAK_RE.split(text)
    pieces: list[str] = []
    buf = ""
    for part in parts:
        if not part:
            continue
        candidate = buf + part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            pieces.append(buf.strip())
            buf = part
        while len(buf) > max_chars:
            pieces.append(buf[:max_chars].strip())
            buf = buf[max_chars:]
    if buf.strip():
        pieces.append(buf.strip())
    return [p for p in pieces if p]


def _split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT_RE.split(text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > _MAX_SENTENCE_CHARS:
            line_parts = [s.strip() for s in p.split("\n") if s.strip()] or [p]
            for s in line_parts:
                out.extend(_split_long_sentence(s))
        else:
            out.append(p)
    return out


def _flatten_pages(pages: list[PageText]) -> list[ParsedBlock]:
    """Legacy fallback: when pages have no blocks, synthesise one per page."""
    blocks: list[ParsedBlock] = []
    for p in pages:
        if p.blocks:
            blocks.extend(p.blocks)
        elif p.text:
            blocks.append(
                ParsedBlock(
                    page=p.page,
                    block_type="text",
                    text=p.text,
                    bbox=(0.0, 0.0, 0.0, 0.0),
                )
            )
    return blocks


def _sentences_from_blocks(blocks: list[ParsedBlock]) -> list[_Sent]:
    flat: list[_Sent] = []
    for idx, b in enumerate(blocks):
        for s in _split_sentences(b.text):
            flat.append((b.page, idx, b.block_type, b.bbox, s))
    return flat


def _bbox_union(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    # Treat (0,0,0,0) as uninitialised
    if a == (0.0, 0.0, 0.0, 0.0):
        return b
    if b == (0.0, 0.0, 0.0, 0.0):
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def chunk_blocks(
    blocks: list[ParsedBlock],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[ChunkPiece]:
    flat = _sentences_from_blocks(blocks)

    chunks: list[ChunkPiece] = []
    buf: list[_Sent] = []
    buf_len = 0
    seq = 0

    def assemble_text(items: list[_Sent]) -> str:
        """Group by block_idx; sentences within a block join tightly, blocks separated by \\n\\n."""
        out: list[str] = []
        cur_block_idx: int | None = None
        cur_parts: list[str] = []
        for _page, bidx, _btype, _bbox, s in items:
            if bidx != cur_block_idx:
                if cur_parts:
                    out.append("".join(cur_parts).strip())
                cur_parts = [s]
                cur_block_idx = bidx
            else:
                # Within a block: space between ASCII-alpha boundaries, else concatenate
                if cur_parts and cur_parts[-1] and cur_parts[-1][-1].isascii() and cur_parts[-1][-1].isalpha():
                    cur_parts.append(" " + s)
                else:
                    cur_parts.append(s)
        if cur_parts:
            out.append("".join(cur_parts).strip())
        return "\n\n".join(x for x in out if x).strip()

    def compute_ranges(
        items: list[_Sent],
    ) -> tuple[int, int | None, list[str], list[dict], list[dict], list[dict]]:
        pages_seq = [it[0] for it in items]
        first_page = pages_seq[0]
        last_page = pages_seq[-1]
        # Per page, union bbox over blocks that fall on that page
        per_page: dict[int, tuple[float, float, float, float]] = {}
        seen_block_ids: set[tuple[int, int]] = set()  # (page, bidx)
        block_types: list[str] = []
        tables: list[dict] = []
        formulas: list[dict] = []
        for page, bidx, btype, bbox, _s in items:
            if (page, bidx) in seen_block_ids:
                continue
            seen_block_ids.add((page, bidx))
            block_types.append(btype)
            per_page[page] = _bbox_union(per_page.get(page, (0.0, 0.0, 0.0, 0.0)), bbox)
            # Pull the matching ParsedBlock's extras so downstream layers
            # (prompt builder, QA, UI) can see the structured body even though
            # the chunk text only carries caption/placeholder.
            if 0 <= bidx < len(blocks):
                extras = blocks[bidx].extras or {}
                if btype == "table":
                    html = (extras.get("table_html") or "").strip()
                    if html:
                        tables.append(
                            {
                                "page": page,
                                "caption": (extras.get("caption") or "").strip(),
                                "footnote": (extras.get("footnote") or "").strip(),
                                "text": (extras.get("table_text") or "").strip(),
                                "html": html,
                            }
                        )
                elif btype == "formula":
                    latex = (extras.get("latex") or "").strip()
                    if latex:
                        formulas.append({"page": page, "latex": latex})
        ranges = [
            {"page": p, "bbox": list(per_page[p])}
            for p in sorted(per_page.keys())
            if per_page[p] != (0.0, 0.0, 0.0, 0.0)
        ]
        return (
            first_page,
            (last_page if last_page != first_page else None),
            block_types,
            ranges,
            tables,
            formulas,
        )

    def flush(*, carry_overlap: bool = True):
        nonlocal seq, buf, buf_len
        if not buf:
            return
        text = assemble_text(buf)
        if not text:
            buf = []
            buf_len = 0
            return
        # Final sanity sieve — parser-level filtering catches most trash, but a
        # chunk can still end up dominated by noisy sentences aggregated across
        # blocks. Skip it here rather than polluting the vector index.
        # Title-only / figure_caption chunks are short and legitimate, so the
        # `min_len` exempts them via is_noise_block's default.
        if is_noise_block(text):
            # Reset buffer but do not emit — also do not carry overlap (would
            # re-propagate the same noise into the next chunk).
            buf = []
            buf_len = 0
            return
        first_page, page_end, btypes, ranges, tables, formulas = compute_ranges(buf)
        chunks.append(
            ChunkPiece(
                seq=seq,
                text=text,
                page=first_page,
                char_count=len(text),
                page_end=page_end,
                block_types=btypes,
                bbox_ranges=ranges,
                tables=tables,
                formulas=formulas,
            )
        )
        seq += 1

        if carry_overlap and chunk_overlap > 0 and len(text) > chunk_overlap:
            # Overlap: carry last sentence(s) up to chunk_overlap chars
            tail: list[_Sent] = []
            acc = 0
            for item in reversed(buf):
                tail.insert(0, item)
                acc += len(item[4])
                if acc >= chunk_overlap:
                    break
            buf = tail
            buf_len = sum(len(it[4]) for it in buf)
        else:
            buf = []
            buf_len = 0

    for sent in flat:
        s_len = len(sent[4])
        if buf_len + s_len > chunk_size and buf_len > 0:
            flush()
        buf.append(sent)
        buf_len += s_len
        if buf_len >= chunk_size * 1.5:
            flush()

    # Final flush must not carry overlap. Otherwise the carried tail from the
    # last real chunk is emitted again as a duplicate short chunk.
    flush(carry_overlap=False)
    return chunks


def chunk_pages(
    pages: list[PageText],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[ChunkPiece]:
    """Backwards-compatible entrypoint used by ingest.py."""
    return chunk_blocks(
        _flatten_pages(pages), chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
