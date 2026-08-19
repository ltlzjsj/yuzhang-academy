"""Cheap relevance gate for deciding whether retrieved RAG context is usable.

The retriever will always find *something* in a non-empty vector collection.
This module decides whether those hits are strong enough to be shown to the
LLM/user, so unrelated chats do not get polluted with arbitrary citations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.rag.retriever import RetrievedChunk

_ASCII_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{1,}")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
_SMALL_TALK_RE = re.compile(
    r"^\s*(?:hi|hello|hey|thanks|thank you|你好|您好|谢谢|多谢|早上好|晚上好|在吗|你是谁|你叫什么)"
    r"[\s。！？!?.~～]*$",
    re.I,
)

_ASCII_STOP = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "what",
    "with",
    "you",
}

_CJK_STOP_CHARS = set("的一是在和与或及了着过这那哪什么怎么如何请帮我你他她它吗呢吧啊")


@dataclass
class RagGateDecision:
    use_context: bool
    reason: str
    overlap: float = 0.0
    best_rrf: float = 0.0
    best_vector: float = 0.0
    best_qa: float = 0.0
    best_bm25: float = 0.0


def should_attempt_rag(query: str) -> bool:
    """Return False for obvious chit-chat / empty queries before retrieval."""
    q = (query or "").strip()
    if len(q) < 2:
        return False
    if _SMALL_TALK_RE.match(q):
        return False
    return True


def decide_rag_context(query: str, retrieved: list[RetrievedChunk]) -> RagGateDecision:
    """Decide whether retrieved chunks are relevant enough to inject."""
    if not retrieved:
        return RagGateDecision(False, "no_hits")

    q_terms = _terms(query)
    if not q_terms:
        return RagGateDecision(False, "no_query_terms")

    top_text = "\n".join(_chunk_text_for_gate(r) for r in retrieved[:3])
    c_terms = _terms(top_text)
    overlap = len(q_terms & c_terms) / max(1, len(q_terms))

    best_rrf = max((r.score for r in retrieved), default=0.0)
    best_vector = max((_retrieval_score(r, "vector") for r in retrieved), default=0.0)
    best_qa = max((_retrieval_score(r, "qa") for r in retrieved), default=0.0)
    best_bm25 = max((_retrieval_score(r, "bm25") for r in retrieved), default=0.0)

    min_overlap = float(settings.rag_gate_min_overlap)
    min_rrf = float(settings.rag_gate_min_rrf)
    strong_rrf = float(settings.rag_gate_strong_rrf)
    min_vector = float(settings.rag_gate_min_vector)
    min_qa = float(settings.rag_gate_min_qa)

    if best_rrf >= strong_rrf:
        return RagGateDecision(True, "strong_rrf", overlap, best_rrf, best_vector, best_qa, best_bm25)
    if best_vector >= min_vector:
        return RagGateDecision(True, "strong_vector", overlap, best_rrf, best_vector, best_qa, best_bm25)
    if best_qa >= min_qa:
        return RagGateDecision(True, "strong_qa", overlap, best_rrf, best_vector, best_qa, best_bm25)
    if best_rrf >= min_rrf and overlap >= min_overlap:
        return RagGateDecision(True, "rrf_plus_overlap", overlap, best_rrf, best_vector, best_qa, best_bm25)
    if overlap >= max(min_overlap * 2.0, 0.34) and (best_rrf > 0 or best_bm25 > 0):
        return RagGateDecision(True, "high_overlap", overlap, best_rrf, best_vector, best_qa, best_bm25)
    return RagGateDecision(False, "weak_relevance", overlap, best_rrf, best_vector, best_qa, best_bm25)


def _terms(text: str) -> set[str]:
    text = text or ""
    terms: set[str] = set()
    for m in _ASCII_RE.finditer(text):
        tok = m.group(0).lower()
        if tok not in _ASCII_STOP and len(tok) >= 2:
            terms.add(tok)
    for run_m in _CJK_RUN_RE.finditer(text):
        run = "".join(ch for ch in run_m.group(0) if ch not in _CJK_STOP_CHARS)
        if len(run) >= 2:
            terms.update(run[i : i + 2] for i in range(len(run) - 1))
            if len(run) >= 3:
                terms.update(run[i : i + 3] for i in range(len(run) - 2))
        elif run:
            terms.add(run)
    return terms


def _chunk_text_for_gate(r: RetrievedChunk) -> str:
    parts = [r.text or ""]
    if r.meta:
        for t in r.meta.get("tables") or []:
            parts.append(t.get("caption") or "")
            parts.append(t.get("text") or "")
        for f in r.meta.get("formulas") or []:
            parts.append(f.get("latex") or "")
    return "\n".join(p for p in parts if p)


def _retrieval_score(r: RetrievedChunk, name: str) -> float:
    if not r.meta:
        return 0.0
    scores = r.meta.get("_retrieval") or {}
    try:
        return float(scores.get(name) or 0.0)
    except (TypeError, ValueError):
        return 0.0
