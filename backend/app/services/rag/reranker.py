"""Cross-encoder reranker for the retriever's fused candidate list.

Model: `BAAI/bge-reranker-v2-m3` — multilingual, ~600 MB, matches our
bge-m3 embedder family. Outputs a single logit per (query, chunk) pair;
higher = more relevant.

Why transformers instead of sentence-transformers:
- `transformers` ships with torch already (MinerU pulls it in) — zero new deps.
- The rerank forward pass is just one `AutoModelForSequenceClassification`
  call, which is trivial to drive directly.

Degradation policy:
- Lazy import inside `rerank()` so the rest of RAG still works if transformers
  ever breaks.
- Any failure inside rerank is logged and the original ordering is returned —
  rerank is a quality booster, not a hard dependency.
- First call downloads the model (uses `settings.hf_endpoint` for mirror).
  Subsequent calls hit the HuggingFace local cache.

The singleton is guarded with a lock so the first concurrent request doesn't
trigger two model loads.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Sequence

from app.core.config import settings

log = logging.getLogger(__name__)

_MODEL = None
_TOKENIZER = None
_DEVICE: str | None = None
_LOAD_LOCK = threading.Lock()
_LOAD_FAILED = False


def _load_once() -> bool:
    """Load model + tokenizer once. Return True on success, False if permanently disabled."""
    global _MODEL, _TOKENIZER, _DEVICE, _LOAD_FAILED
    if _MODEL is not None:
        return True
    if _LOAD_FAILED:
        return False
    with _LOAD_LOCK:
        if _MODEL is not None:
            return True
        if _LOAD_FAILED:
            return False
        try:
            os.environ.setdefault("HF_ENDPOINT", settings.hf_endpoint)
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            name = settings.rerank_model
            log.info("reranker: loading %s …", name)
            tok = AutoTokenizer.from_pretrained(name)
            mdl = AutoModelForSequenceClassification.from_pretrained(name)
            device = (
                "cuda"
                if settings.rerank_device == "auto" and torch.cuda.is_available()
                else ("cuda" if settings.rerank_device == "cuda" else "cpu")
            )
            mdl = mdl.to(device).eval()
            _MODEL = mdl
            _TOKENIZER = tok
            _DEVICE = device
            log.info("reranker ready on %s", device)
            return True
        except Exception as e:
            log.warning("reranker load failed: %s — disabling rerank this process", e)
            _LOAD_FAILED = True
            return False


def rerank_scores(query: str, candidates: Sequence[str], *, batch_size: int = 16) -> list[float] | None:
    """Return a relevance score for each candidate, or None if rerank disabled.

    Higher score = more relevant. Length matches `candidates`.
    """
    if not candidates:
        return []
    if not _load_once():
        return None

    import torch

    assert _MODEL is not None and _TOKENIZER is not None
    pairs = [(query, c) for c in candidates]
    scores: list[float] = []
    try:
        with torch.inference_mode():
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i : i + batch_size]
                enc = _TOKENIZER(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                ).to(_DEVICE)
                logits = _MODEL(**enc).logits.view(-1).float().cpu().tolist()
                scores.extend(logits)
    except Exception as e:
        log.warning("reranker forward failed: %s — falling back to fused order", e)
        return None
    return scores


def rerank(query: str, items: list, *, text_key: str = "text") -> list:
    """Reorder `items` (list of objects/dicts) by cross-encoder relevance to `query`.

    Returns a new list sorted descending by rerank score. If rerank is
    unavailable for any reason, returns `items` unchanged.
    """
    if not items:
        return items
    texts = [getattr(it, text_key, None) or (it.get(text_key) if isinstance(it, dict) else "") for it in items]
    scores = rerank_scores(query, texts)
    if scores is None:
        return items
    order = sorted(range(len(items)), key=lambda i: scores[i], reverse=True)
    return [items[i] for i in order]
