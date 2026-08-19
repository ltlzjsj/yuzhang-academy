"""Text quality heuristics for RAG ingest.

Why a dedicated module:
- MinerU's layout model occasionally mis-classifies stray table rows, math
  debris, or figure-embedded labels as `type=text`. Those blocks are dense
  with digits / LaTeX commands / punctuation and dilute the embeddings when
  they land in a chunk.
- We can't trust `block_type` alone — heuristics on the *text itself* are the
  final sieve before indexing.

The checks here are intentionally lightweight and conservative: we'd rather
keep a marginal chunk than drop real content. Tune `NOISE_LETTER_RATIO` down
if you see legitimate chunks being filtered; tune it up if garbage still
slips through.
"""
from __future__ import annotations

import re

# Any `\alpha`, `\frac`, `\begin{...}`, etc. A single pattern catches the common cases.
_LATEX_CMD_RE = re.compile(r"\\[A-Za-z]+\*?(?:\s*\{[^{}]*\})*")
# LaTeX delimiters we strip as standalone noise (rare in legitimate prose)
_LATEX_DELIM_RE = re.compile(r"\$\$?|\\\(|\\\)|\\\[|\\\]")
# Isolated braces / backslashes left behind after cleanup
_LATEX_REMNANT_RE = re.compile(r"[{}\\]")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"[0-9]")

# Below this letter ratio, a long block is almost certainly table/formula debris.
NOISE_LETTER_RATIO = 0.30
# Short blocks (e.g. captions "图 3") are exempt from the ratio test.
NOISE_MIN_LEN = 30
# If a text block has this many LaTeX commands per 100 chars, it's formula debris.
NOISE_LATEX_DENSITY = 0.04


def letter_ratio(text: str) -> float:
    if not text:
        return 0.0
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return 0.0
    letters = len(_CJK_RE.findall(compact)) + len(_ASCII_ALPHA_RE.findall(compact))
    return letters / len(compact)


def digit_ratio(text: str) -> float:
    if not text:
        return 0.0
    compact = re.sub(r"\s+", "", text)
    if not compact:
        return 0.0
    return len(_DIGIT_RE.findall(compact)) / len(compact)


def latex_command_density(text: str) -> float:
    if not text:
        return 0.0
    n = len(_LATEX_CMD_RE.findall(text))
    return n / max(1, len(text)) * 100  # commands per 100 chars


def strip_latex_islands(text: str) -> str:
    """Remove stray LaTeX commands/delimiters that leaked outside `$...$` blocks.

    MinerU sometimes emits fragments like `\\mathrm{ x } = 0.5 \\times 10^{-3}`
    inline with real prose. We drop the commands and collapse whitespace; if
    the result is still mostly digits/punctuation, `is_noise_block` will kill
    the whole chunk downstream anyway.
    """
    if not text or "\\" not in text:
        return text
    cleaned = _LATEX_CMD_RE.sub(" ", text)
    cleaned = _LATEX_DELIM_RE.sub(" ", cleaned)
    cleaned = _LATEX_REMNANT_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
    return cleaned.strip()


def is_noise_block(text: str, *, min_len: int = NOISE_MIN_LEN) -> bool:
    """True if the text is probably a misclassified table row / formula fragment.

    Rules:
    - very short blocks are always kept (captions, list items)
    - long blocks with letter_ratio below threshold → drop
    - dense LaTeX commands → drop
    """
    if not text:
        return True
    compact = text.strip()
    if len(compact) < min_len:
        return False  # too short to judge; keep
    if letter_ratio(compact) < NOISE_LETTER_RATIO:
        return True
    if latex_command_density(compact) >= NOISE_LATEX_DENSITY:
        return True
    return False
