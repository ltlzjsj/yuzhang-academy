"""Hybrid retriever: Qdrant vector search + in-memory BM25, fused via RRF.

Why in-memory BM25:
- MySQL FULLTEXT doesn't ship a good CJK tokenizer out of the box.
- Our KB sizes (target: <= a few 10k chunks per KB) fit comfortably in RAM.
- `rank_bm25` is pure-Python and tokenisation is ours to control.

Tokenisation: very light — CJK chars are individual tokens, ASCII words
are split on whitespace/punct. Works well with BGE-M3's recall as a coarse
lexical sieve; the vector channel carries the semantic weight.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.academies import detect_academies
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.rag.bm25_cache import score_query as bm25_score_query
from app.services.rag.embedder import embed_texts
from app.services.rag.reranker import rerank as cross_encoder_rerank
from app.services.vector_store import (
    collection_name_for_kb,
    search_points,
    search_qa_points,
)

log = logging.getLogger(__name__)

@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    kb_id: int
    page: int | None
    bbox: list | dict | None
    filename: str
    text: str
    score: float  # fused RRF score
    meta: dict | None = None  # M5: structured extras (tables/formulas)


def _rrf_fuse(
    rankings: list[list[int]],
    weights: list[float] | None = None,
    k: int = 60,
) -> dict[int, float]:
    """Weighted Reciprocal Rank Fusion over multiple ranked lists of chunk_ids.

    `weights` — per-channel multiplier; missing/empty defaults to all-1.0.
    Why weights: the QA channel has a much smaller candidate pool than vector
    or BM25, so without a boost its good hits get diluted at fusion time.
    """
    if weights is None or len(weights) != len(rankings):
        weights = [1.0] * len(rankings)
    scores: dict[int, float] = {}
    for ranked, w in zip(rankings, weights):
        if w <= 0:
            continue
        seen_in_channel: set[int] = set()
        for rank, cid in enumerate(ranked):
            if cid is None:
                continue
            if cid in seen_in_channel:
                continue
            seen_in_channel.add(cid)
            scores[cid] = scores.get(cid, 0.0) + w / (k + rank)
    return scores


def _rank_ids_by_score(scores: dict[int, float]) -> list[int]:
    return [cid for cid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


def _better_qa_hit(current: dict | None, hit: dict) -> bool:
    if current is None:
        return True
    return float(hit.get("score") or 0.0) > float(current.get("score") or 0.0)


def retrieve(
    db: Session,
    kb_ids: list[int],
    query: str,
    top_k: int = 6,
    per_channel_k: int = 20,
    embed_model: str | None = None,
    rerank: bool = False,
) -> list[RetrievedChunk]:
    """Hybrid retrieve across one or more KBs. Returns top_k fused chunks.

    When `rerank` is True, the fused top `top_k * rerank_candidate_factor`
    candidates are re-ordered by a cross-encoder (see `reranker.py`) before
    truncating to `top_k`. The reranker silently degrades to a no-op if the
    model can't load, so callers always get a best-effort result.
    """
    if not kb_ids or not query.strip():
        return []

    query = query.strip()

    # When rerank is on, oversample candidates so the cross-encoder has room
    # to promote chunks that BM25+vector ranked lower.
    candidate_k = top_k * settings.rerank_candidate_factor if rerank else top_k

    # --- Channel 1: vector search (Qdrant) ---
    # Disabled in the 书院/MiMo build (no local embedding model). When off we
    # skip embed + Qdrant entirely and rely on BM25 keyword retrieval below.
    vector_scores: dict[int, float] = {}
    qa_scores: dict[int, float] = {}
    matched_qa: dict[int, dict] = {}
    vec = None
    if settings.rag_vector_enabled:
        try:
            vec = embed_texts([query], model=embed_model)[0]
        except Exception as e:
            log.warning("embed failed: %s — vector channel disabled", e)
            vec = None

    if vec is not None:
        for kb_id in kb_ids:
            collection = collection_name_for_kb(kb_id)
            hits = search_points(collection, vec, limit=per_channel_k)
            for h in hits:
                if float(h.get("score") or 0) < settings.rag_min_vector_score:
                    continue
                cid = h.get("chunk_id")
                if cid is not None:
                    cid_int = int(cid)
                    vector_scores[cid_int] = max(
                        vector_scores.get(cid_int, 0.0), float(h.get("score") or 0.0)
                    )
            # QA channel — question-embedded points linked back to their chunk.
            # Uses its own limit (smaller corpus) and is weighted higher at fusion.
            qa_hits = search_qa_points(collection, vec, limit=settings.rag_qa_k)
            for h in qa_hits:
                if float(h.get("score") or 0) < settings.rag_min_qa_score:
                    continue
                cid = h.get("chunk_id")
                if cid is not None:
                    cid_int = int(cid)
                    score = float(h.get("score") or 0.0)
                    qa_scores[cid_int] = max(qa_scores.get(cid_int, 0.0), score)
                    qa_hit = {
                        "qa_id": h.get("qa_id"),
                        "question": h.get("question"),
                        "answer": h.get("answer"),
                        "score": score,
                    }
                    if _better_qa_hit(matched_qa.get(cid_int), qa_hit):
                        matched_qa[cid_int] = qa_hit
            if qa_hits:
                log.info(
                    "retrieve qa top: %s",
                    [(h.get("qa_id"), (h.get("question") or "")[:40], round(h.get("score") or 0, 3)) for h in qa_hits[:3]],
                )

    # --- Channel 2: BM25 (cached per KB) ---
    # The cache invalidates on ingest/delete; normal read path skips the DB
    # corpus pull and tokenisation entirely.
    bm25_scores: dict[int, float] = {}
    for kb_id in kb_ids:
        try:
            hits = bm25_score_query(db, kb_id, query, per_channel_k)
            for cid, score in hits:
                bm25_scores[cid] = max(bm25_scores.get(cid, 0.0), float(score or 0.0))
        except Exception as e:
            log.warning("BM25 failed for KB %d: %s", kb_id, e)

    # --- Fuse (3 channels when QA is present) ---
    vector_ranked_ids = _rank_ids_by_score(vector_scores)
    bm25_ranked_ids = _rank_ids_by_score(bm25_scores)
    qa_ranked_ids = _rank_ids_by_score(qa_scores)
    log.info(
        "retrieve channels: vector=%d bm25=%d qa=%d",
        len(vector_ranked_ids),
        len(bm25_ranked_ids),
        len(qa_ranked_ids),
    )
    fused = _rrf_fuse(
        [vector_ranked_ids, bm25_ranked_ids, qa_ranked_ids],
        weights=[
            settings.rag_weight_vector,
            settings.rag_weight_bm25,
            settings.rag_weight_qa,
        ],
    )
    if not fused:
        return []
    min_rrf = float(settings.rag_min_rrf or 0)
    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    if min_rrf > 0:
        ranked = [(cid, s) for cid, s in ranked if s >= min_rrf]
    top_ids = [cid for cid, _ in ranked[:candidate_k]]

    # --- Hydrate full chunk rows + document filename ---
    chunks = (
        db.query(Chunk, Document.filename)
        .join(Document, Document.id == Chunk.document_id)
        .filter(Chunk.id.in_(top_ids))
        .all()
    )
    by_id = {c.id: (c, fn) for c, fn in chunks}
    out: list[RetrievedChunk] = []
    for cid in top_ids:
        if cid not in by_id:
            continue
        c, fn = by_id[cid]
        meta = dict(c.meta or {})
        meta["_retrieval"] = {
            "rrf": float(fused[cid]),
            "vector": vector_scores.get(cid, 0.0),
            "bm25": bm25_scores.get(cid, 0.0),
            "qa": qa_scores.get(cid, 0.0),
        }
        if cid in matched_qa:
            meta["_matched_qa"] = matched_qa[cid]
        out.append(
            RetrievedChunk(
                chunk_id=c.id,
                document_id=c.document_id,
                kb_id=c.kb_id,
                page=c.page,
                bbox=c.bbox,
                filename=fn,
                text=c.text,
                score=float(fused[cid]),
                meta=meta,
            )
        )

    # --- Academy-name boost ---
    # When the question names a specific 书院, promote chunks whose text mentions
    # that academy so its own section wins over incidental matches elsewhere in
    # the book. Applied before rerank/truncation so a strong name hit survives.
    names = detect_academies(query)
    if names and out:
        def _name_bonus(r: RetrievedChunk) -> float:
            text = r.text or ""
            return 0.05 * sum(1 for n in names if n in text)

        out.sort(key=lambda r: r.score + _name_bonus(r), reverse=True)

    # --- Rerank (optional) ---
    if rerank and out:
        reordered = cross_encoder_rerank(query, out, text_key="text")
        # Cap to top_k after rerank. If rerank degraded, `out` is returned as-is
        # and we still cap to top_k — keeping behaviour equivalent to rerank=False
        # for the caller.
        out = reordered[:top_k]
    else:
        out = out[:top_k]
    return out
