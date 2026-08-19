"""Shared data structures for PDF parsers (legacy + MinerU).

Keeps the (pages, total) contract so ingest.py stays stable while
exposing per-block structure (bbox, type, level) for the new pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BlockType = Literal[
    "text",
    "title",
    "table",
    "figure",
    "figure_caption",
    "table_caption",
    "formula",
    "equation",
    "header",
    "footer",
    "page_number",
    "other",
]


@dataclass
class ParsedBlock:
    page: int  # 1-indexed
    block_type: BlockType
    text: str  # cleaned, paragraph-joined
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 — MinerU 0-1000 normalized
    level: int | None = None  # heading level 1..6 (titles only)
    extras: dict = field(default_factory=dict)  # latex, table_html, etc


@dataclass
class PageText:
    page: int  # 1-indexed
    text: str
    char_count: int
    blocks: list[ParsedBlock] = field(default_factory=list)
