"""Choose a PDF parser based on settings, with legacy fallback on failure."""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.services.parser_types import PageText

log = logging.getLogger(__name__)


def parse_pdf(path: str | Path) -> tuple[list[PageText], int]:
    """Unified entrypoint used by ingest. Returns (pages, total)."""
    path = Path(path)
    parser = (settings.pdf_parser or "mineru").lower()

    if parser == "mineru":
        try:
            from app.services.mineru_parser import parse_with_mineru

            return parse_with_mineru(path)
        except Exception as e:  # pragma: no cover — defensive
            log.warning(
                "MinerU failed on %s (%s). Falling back to legacy parser.",
                path.name,
                e,
            )

    # Legacy: returns PageText objects without .blocks → we re-wrap to share type
    from app.services.pdf_parser import parse_pdf as legacy_parse

    legacy_pages, total = legacy_parse(path)
    wrapped: list[PageText] = [
        PageText(page=p.page, text=p.text, char_count=p.char_count, blocks=[])
        for p in legacy_pages
    ]
    return wrapped, total
