"""Per-KB in-memory BM25 index cache.

Why:
- The retriever used to pull the entire chunk corpus from MySQL, tokenise it,
  and build a BM25Okapi index on every chat request. For a 5k-chunk KB that's
  300–1000 ms of pure waste, since the corpus only changes on ingest/delete.
- We cache `(ids, BM25Okapi)` per KB. Scoring a new query then costs O(|Q|·|D|)
  vector-ish work only, and the DB stays out of the hot path entirely.

Invalidation contract:
- `invalidate(kb_id)` MUST be called after any write to `chunks` for that KB
  (ingest / reingest / delete). Wired at the end of ingest.py + documents.py.
- A simple row-count + max-id signature is recorded when the cache is built.
  If the signature no longer matches on read (another process wrote), we
  transparently rebuild. Belt-and-braces for multi-worker setups.

Thread-safety: guarded by a lock per KB (fine-grained; concurrent KBs don't
block each other).
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chunk import Chunk

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


@dataclass
class _Entry:
    kb_id: int
    ids: list[int]
    bm25: BM25Okapi
    row_count: int
    max_id: int


_cache: dict[int, _Entry] = {}
_locks: dict[int, threading.Lock] = {}
_cache_lock = threading.Lock()


def _lock_for(kb_id: int) -> threading.Lock:
    with _cache_lock:
        lk = _locks.get(kb_id)
        if lk is None:
            lk = threading.Lock()
            _locks[kb_id] = lk
        return lk


def _signature(db: Session, kb_id: int) -> tuple[int, int]:
    """Cheap change-detection signature: (row_count, max_id). One query, indexed."""
    row = (
        db.query(func.count(Chunk.id), func.coalesce(func.max(Chunk.id), 0))
        .filter(Chunk.kb_id == kb_id)
        .one()
    )
    return int(row[0]), int(row[1])


def _build(db: Session, kb_id: int) -> _Entry | None:
    rows = db.query(Chunk.id, Chunk.text).filter(Chunk.kb_id == kb_id).all()
    if not rows:
        return None
    ids = [r[0] for r in rows]
    corpus = [tokenize(r[1] or "") for r in rows]
    # BM25Okapi copes with empty docs but warns; ensure at least a stub.
    corpus = [toks if toks else ["_empty_"] for toks in corpus]
    bm25 = BM25Okapi(corpus)
    rc, mx = _signature(db, kb_id)
    log.info("bm25_cache: built KB %d (%d docs)", kb_id, len(ids))
    return _Entry(kb_id=kb_id, ids=ids, bm25=bm25, row_count=rc, max_id=mx)


def get_or_build(db: Session, kb_id: int) -> _Entry | None:
    """Return a cached entry for the KB, rebuilding if stale or missing."""
    lk = _lock_for(kb_id)
    with lk:
        entry = _cache.get(kb_id)
        if entry is not None:
            try:
                rc, mx = _signature(db, kb_id)
                if (rc, mx) == (entry.row_count, entry.max_id):
                    return entry
                log.info(
                    "bm25_cache: KB %d signature changed (%s→%s), rebuilding",
                    kb_id, (entry.row_count, entry.max_id), (rc, mx),
                )
            except Exception as e:
                # If signature query fails, trust the cache rather than erroring
                log.warning("bm25_cache: signature check failed for KB %d: %s", kb_id, e)
                return entry
        entry = _build(db, kb_id)
        if entry is not None:
            _cache[kb_id] = entry
        else:
            _cache.pop(kb_id, None)
        return entry


def invalidate(kb_id: int) -> None:
    """Drop the cache entry for `kb_id`. Safe to call on unknown KBs."""
    with _lock_for(kb_id):
        if _cache.pop(kb_id, None) is not None:
            log.info("bm25_cache: invalidated KB %d", kb_id)


def score_query(db: Session, kb_id: int, query: str, top_k: int) -> list[tuple[int, float]]:
    """Return [(chunk_id, score)] of the best `top_k` matches for `query` in `kb_id`.

    Returns an empty list if the KB is empty, query tokenises to nothing, or
    BM25 is unavailable for any reason.
    """
    q_tok = tokenize(query)
    if not q_tok:
        return []
    entry = get_or_build(db, kb_id)
    if entry is None:
        return []
    try:
        scores = entry.bm25.get_scores(q_tok)
    except Exception as e:
        log.warning("bm25_cache: scoring failed KB %d: %s", kb_id, e)
        return []
    # Argsort descending, keep only positive scores
    idxs = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [(entry.ids[i], float(scores[i])) for i in idxs if scores[i] > 0]
