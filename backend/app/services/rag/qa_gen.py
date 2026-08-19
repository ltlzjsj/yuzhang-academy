"""Synchronous QA-pair generator — used by Celery workers.

For each chunk we ask the local LLM to produce 1-3 factual Q/A pairs grounded
ONLY in the chunk text. We then embed the question (question-only, since user
queries are question-shaped) and upsert to Qdrant under the SAME per-KB
collection with ``type="qa"`` and ``chunk_id`` linking back to the source.

Why question-only embeddings:
  - Aligns the vector with how users phrase things (the question channel
    becomes a high-precision sieve for "is this chunk even relevant?").
  - Answers are often too short or too statement-like to retrieve well on
    their own; they're carried as *context* via the linked chunk.

Failure policy: any single chunk failing (parse / Ollama timeout) is logged
and skipped — we never abort the whole task, since partial QA coverage is
still valuable.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

import httpx
from qdrant_client.http import models as qm
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chunk import Chunk, QAPair
from app.models.document import Document, DocumentStatus
from app.models.kb import KnowledgeBase
from app.services.rag.embedder import embed_texts
from app.services.vector_store import (
    collection_name_for_kb,
    ensure_collection,
    get_client,
)

log = logging.getLogger(__name__)

_http_client: httpx.Client | None = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(
            trust_env=False,
            timeout=httpx.Timeout(connect=10, read=600, write=30, pool=10),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
        )
    return _http_client


def _unload_model(model: str) -> None:
    try:
        _get_http_client().post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
            timeout=10,
        )
    except Exception:
        pass


# ---------- prompt ----------

_QA_PROMPT = """/no_think
你是一名地质矿产领域的资深研究员。请阅读下面的一段资料，基于其中**明确陈述**的事实，抽取恰好 {n} 条"问答对"（如内容不足则尽量接近 {n} 条，但不得超过 {n}）。

严格规则：
1. 问题必须能够完全依据本段内容回答，不得引入外部知识或推测。
2. 答案必须简洁、事实性（数字、定义、关系、术语），避免空泛总结。
3. 如果本段过短、过于模糊、或主要是图表/公式占位符，则输出空数组 []。
4. 问题和答案使用与原文一致的语言（中文原文→中文问答；English source→English QA）。
5. 只输出 **JSON 数组**，形如：[{{"q":"...", "a":"..."}}, ...]。不要有任何解释、前言、Markdown 代码围栏。

# 资料
{chunk}

# 输出"""


# Small local LLMs routinely ignore "JSON only" — they wrap with prose,
# fences, Chinese punctuation, or emit a single object instead of an array.
# Normalise aggressively then try several extraction strategies.
_CJK_QUOTE_MAP = str.maketrans(
    {
        "“": '"', "”": '"', "„": '"', "‟": '"',
        "‘": "'", "’": "'", "‚": "'", "‛": "'",
        "，": ",", "：": ":",
    }
)
_OBJ_RE = re.compile(r"\{[^{}]*\}", re.S)


@dataclass
class QAItem:
    question: str
    answer: str


_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


def _call_ollama_generate(model: str, prompt: str, *, num_predict: int = 2048) -> str:
    """Ollama chat (non-streaming). Returns the assistant content string.

    `num_predict` defaults high because thinking-capable models (qwen3, glm-4,
    deepseek-r1 ...) burn tokens on an internal ``<think>...</think>`` trace
    before emitting the user-visible answer. A tight budget lets them run out
    of tokens inside the thinking block, leaving ``content=""``.

    We also:
      - Try ``message.thinking`` when ``content`` is empty (some Ollama builds
        return thinking separately).
      - Strip ``<think>...</think>`` substrings, since the parser only cares
        about the final JSON.
      - Surface Ollama's error body verbatim so model-not-found shows up cleanly
        in the worker log.
    """
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": num_predict,
        },
    }
    r = _get_http_client().post(url, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(
            f"Ollama {r.status_code} for model={model!r}: {r.text[:200]}"
        )
    data = r.json()
    msg = data.get("message") or {}
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("thinking") or "").strip()
    content = _THINK_TAG_RE.sub("", content).strip()
    return content


def _items_from_json(data) -> list[QAItem]:
    """Accepts either a list of objects or a single object with q/a keys."""
    candidates: list = []
    if isinstance(data, list):
        candidates = data
    elif isinstance(data, dict):
        # Either {q:..,a:..} or {pairs:[{q,a},...]} or {qa:[...]}
        inner = data.get("pairs") or data.get("qa") or data.get("items")
        if isinstance(inner, list):
            candidates = inner
        else:
            candidates = [data]
    out: list[QAItem] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        q = (item.get("q") or item.get("question") or item.get("问") or "").strip()
        a = (item.get("a") or item.get("answer") or item.get("答") or "").strip()
        if len(q) >= 4 and len(a) >= 2:
            out.append(QAItem(question=q, answer=a))
    return out[:5]  # hard cap


def _parse_pairs(raw: str) -> list[QAItem]:
    if not raw:
        return []
    text = raw.strip().translate(_CJK_QUOTE_MAP)

    # Strip markdown fences if the model ignored the "no fences" rule
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = text.rsplit("```", 1)[0].strip()

    # Strategy 1: direct parse (best case)
    try:
        return _items_from_json(json.loads(text))
    except Exception:
        pass

    # Strategy 2: slice from first '[' to last ']' and try as array
    lb, rb = text.find("["), text.rfind("]")
    if lb >= 0 and rb > lb:
        snippet = text[lb : rb + 1]
        try:
            items = _items_from_json(json.loads(snippet))
            if items:
                return items
        except Exception:
            pass

    # Strategy 3: regex every {...} object and try each — tolerates junk
    # text between objects and trailing commas.
    objs: list = []
    for m in _OBJ_RE.finditer(text):
        try:
            objs.append(json.loads(m.group(0)))
        except Exception:
            continue
    if objs:
        return _items_from_json(objs)

    return []


def _resolve_qa_model(kb: KnowledgeBase) -> str:
    return (kb.qa_model or settings.default_chat_model).strip()


# ---------- cleanup helpers ----------


def _purge_qa_for_chunks(db: Session, kb_id: int, chunk_ids: list[int]) -> None:
    """Wipe old QA pairs (DB + Qdrant) before regenerating for these chunks."""
    if not chunk_ids:
        return
    # Qdrant: delete by chunk_id payload filter
    try:
        collection = collection_name_for_kb(kb_id)
        get_client().delete(
            collection_name=collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(key="type", match=qm.MatchValue(value="qa")),
                        qm.FieldCondition(key="chunk_id", match=qm.MatchAny(any=chunk_ids)),
                    ]
                )
            ),
            wait=True,
        )
    except Exception as e:  # pragma: no cover — defensive
        log.warning("purge QA vectors failed: %s", e)
    # MySQL: cascade via FK would also handle it on chunk delete, but we're
    # regenerating for still-existing chunks, so remove explicitly.
    db.execute(sa_delete(QAPair).where(QAPair.chunk_id.in_(chunk_ids)))
    db.commit()


def _chunk_text_is_generateable(text: str) -> bool:
    """Cheap heuristic to skip junk chunks before paying for an LLM call."""
    if not text:
        return False
    t = text.strip()
    if len(t) < 80:
        return False
    # Mostly placeholder or figure caption → skip
    letters = sum(1 for ch in t if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    return letters >= 40


# ---------- public entry points ----------


def generate_qa_for_document(
    document_id: int,
    model_override: str | None = None,
    *,
    unload_model: bool = True,
) -> dict:
    """Generate QA pairs for every chunk of one document. Idempotent.

    `model_override` — one-shot model name from the UI. Does NOT persist to the
    KB row; use PATCH /kb/{id} for that. Empty/None falls back to kb.qa_model
    or settings.default_chat_model.
    """
    from app.services.rag.ingest import _session  # reuse its engine

    with _session() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return {"ok": False, "error": "document not found"}
        kb = db.get(KnowledgeBase, doc.kb_id)
        if kb is None or not kb.qa_enabled:
            return {"ok": False, "error": "kb missing or qa disabled"}

        model = (model_override or "").strip() or _resolve_qa_model(kb)
        pairs_target = max(1, min(3, int(kb.qa_pairs_per_chunk or 2)))
        chunks = (
            db.execute(select(Chunk).where(Chunk.document_id == doc.id).order_by(Chunk.seq))
            .scalars()
            .all()
        )
        if not chunks:
            log.info("qa_generate doc_id=%s kb_id=%s chunks=0 skipped=0 pairs=0 failures=0", doc.id, kb.id)
            return {"ok": True, "pairs": 0}

        doc.status = DocumentStatus.qa_generating
        doc.error = None
        db.commit()

        collection = ensure_collection(kb.id)
        total_pairs = 0
        skipped_chunks = 0
        failures: list[str] = []
        generated: list[tuple[Chunk, list[QAItem], list[list[float]]]] = []

        for c in chunks:
            if not _chunk_text_is_generateable(c.text):
                skipped_chunks += 1
                continue
            try:
                raw = _call_ollama_generate(
                    model,
                    _QA_PROMPT.format(chunk=c.text.strip()[:1800], n=pairs_target),
                )
            except Exception as e:
                log.warning("QA generate failed for chunk %d: %s", c.id, e)
                failures.append(f"chunk {c.id}: generate failed")
                continue

            pairs = _parse_pairs(raw)
            if not pairs:
                log.warning(
                    "QA parse produced 0 pairs for chunk %d. Raw head: %r",
                    c.id,
                    (raw or "")[:300],
                )
                skipped_chunks += 1
                continue
            # Respect the per-KB target — small LLMs sometimes ignore "恰好 N 条"
            pairs = pairs[:pairs_target]

            # Embed questions in one batch
            try:
                vectors = embed_texts(
                    [p.question for p in pairs], model=kb.embedding_model
                )
            except Exception as e:
                log.warning("QA embed failed for chunk %d: %s", c.id, e)
                failures.append(f"chunk {c.id}: embed failed")
                continue
            generated.append((c, pairs, vectors))

        # Regeneration is idempotent. Preserve old QA when every attempted
        # generation failed; otherwise replace old rows after new pairs exist.
        should_replace_old = bool(generated) or not failures
        if should_replace_old:
            _purge_qa_for_chunks(db, kb.id, [c.id for c in chunks])
        elif failures:
            doc.status = DocumentStatus.done
            doc.error = "QA 生成失败，已保留旧 Q&A：" + "; ".join(failures[:5])
            db.commit()
            if unload_model:
                _unload_model(model)
            log.info(
                "qa_generate doc_id=%s kb_id=%s chunks=%s skipped=%s pairs=0 failures=%s model=%s preserved_old=true",
                doc.id,
                kb.id,
                len(chunks),
                skipped_chunks,
                len(failures),
                model,
            )
            return {"ok": False, "pairs": 0, "errors": failures}

        for c, pairs, vectors in generated:
            rows: list[QAPair] = []
            for p in pairs:
                rows.append(
                    QAPair(
                        chunk_id=c.id,
                        kb_id=kb.id,
                        question=p.question,
                        answer=p.answer,
                    )
                )
            db.add_all(rows)
            db.commit()
            for r in rows:
                db.refresh(r)

            points: list[qm.PointStruct] = []
            for p, v, row in zip(pairs, vectors, rows):
                pid = str(uuid.uuid4())
                row.qdrant_point_id = pid
                points.append(
                    qm.PointStruct(
                        id=pid,
                        vector=v,
                        payload={
                            "type": "qa",
                            "kb_id": kb.id,
                            "document_id": doc.id,
                            "chunk_id": c.id,
                            "qa_id": row.id,
                            "question": p.question[:500],
                            "answer": p.answer[:500],
                            "filename": doc.filename,
                            "page": c.page,
                        },
                    )
                )
            try:
                get_client().upsert(collection_name=collection, points=points, wait=True)
                db.commit()
                total_pairs += len(points)
            except Exception as e:
                log.warning("QA upsert failed for chunk %d: %s", c.id, e)
                failures.append(f"chunk {c.id}: qdrant upsert failed")

        doc.status = DocumentStatus.done
        doc.error = (
            "QA 生成部分失败：" + "; ".join(failures[:5])
            if failures
            else None
        )
        db.commit()

        # Best-effort unload the QA model so it doesn't sit resident alongside
        # the chat model. KB-wide generation disables this per-doc and unloads once.
        if unload_model:
            _unload_model(model)

        log.info(
            "qa_generate doc_id=%s kb_id=%s chunks=%s skipped=%s pairs=%s failures=%s model=%s",
            doc.id,
            kb.id,
            len(chunks),
            skipped_chunks,
            total_pairs,
            len(failures),
            model,
        )
        return {"ok": not failures, "pairs": total_pairs, "errors": failures}


def generate_qa_for_kb(kb_id: int, model_override: str | None = None) -> dict:
    """Fan-out across every doc in a KB. Best-effort; continues on per-doc failure."""
    from app.services.rag.ingest import _session

    with _session() as db:
        kb = db.get(KnowledgeBase, kb_id)
        model = (model_override or "").strip() or (_resolve_qa_model(kb) if kb else settings.default_chat_model)
        docs = (
            db.execute(select(Document).where(Document.kb_id == kb_id)).scalars().all()
        )
        doc_ids = [d.id for d in docs]

    total = 0
    errors: list[str] = []
    for did in doc_ids:
        try:
            res = generate_qa_for_document(
                did,
                model_override=model,
                unload_model=False,
            )
            total += int(res.get("pairs", 0))
            errors.extend(str(e) for e in (res.get("errors") or []))
        except Exception as e:
            log.warning("QA doc %d failed: %s", did, e)
            errors.append(f"doc {did}: {e}")
    _unload_model(model)
    return {"ok": not errors, "pairs": total, "docs": len(doc_ids), "errors": errors}
