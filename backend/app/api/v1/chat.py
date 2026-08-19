import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.db import get_db, SessionLocal
from app.core.deps import get_current_user
from app.models.conversation import Conversation, Message
from app.models.kb import KBMember, KnowledgeBase
from app.models.user import User
from app.schemas.chat import ChatSendIn
from app.services.academies import detect_academies, images_for_academies
from app.services.llm import chat_stream as llm_chat_stream
from app.services.ollama_client import ollama
from app.services.rag.context import build_rag_system_prompt, citations_payload, collect_images
from app.services.rag.gate import decide_rag_context, should_attempt_rag
from app.services.rag.reranker import rerank as cross_encoder_rerank
from app.services.rag.retriever import retrieve

log = logging.getLogger(__name__)

# Synchronous engine for retriever (rank_bm25 + embed are blocking anyway)
_sync_engine = None
_SyncSession: sessionmaker | None = None


def _get_sync_session() -> Session:
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(settings.alembic_database_uri, pool_pre_ping=True)
        _SyncSession = sessionmaker(_sync_engine, expire_on_commit=False)
    return _SyncSession()

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _image_root(kind: str | None) -> Path:
    """Filesystem root for an image `kind`: curated academy images vs MinerU."""
    if kind == "academy":
        return Path(settings.academy_images_dir)
    return Path(settings.mineru_output_dir)


def _encode_image_downscaled(fp: Path, max_dim: int = 1024, quality: int = 80) -> dict:
    """Downscale + re-encode an image to JPEG base64 for the multimodal LLM.

    The curated photos can be 10MB+ each; sending originals would blow up the
    request body (and MiMo may reject it). We cap the long edge to `max_dim`
    and re-encode as JPEG, which brings each image down to ~100–200KB.
    """
    from io import BytesIO
    from PIL import Image

    with Image.open(fp) as img:
        img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
    return {
        "media_type": "image/jpeg",
        "data": base64.b64encode(buf.getvalue()).decode("ascii"),
    }


def _load_images_b64(images: list[dict], limit: int) -> list[dict]:
    """Resolve collected image `src` paths under their root (academy/mineru),
    downscale, and base64-encode up to `limit` of them for the multimodal LLM."""
    out: list[dict] = []
    for im in images:
        if len(out) >= limit:
            break
        src = (im.get("src") or "").lstrip("/")
        if not src:
            continue
        root = _image_root(im.get("kind"))
        fp = (root / src).resolve()
        # Containment guard: never read outside the assets root.
        try:
            fp.relative_to(root.resolve())
        except ValueError:
            continue
        if not fp.is_file():
            continue
        try:
            out.append(_encode_image_downscaled(fp))
        except Exception as e:
            log.warning("failed to encode image %s: %s", fp, e)
    return out


def _run_retrieve(kb_ids: list[int], query: str, top_k: int, rerank: bool = False):
    """Run hybrid retrieval synchronously on a fresh DB session (called via asyncio.to_thread)."""
    with _get_sync_session() as db:
        return retrieve(db, kb_ids, query, top_k=top_k, rerank=rerank)


def _run_rerank(query: str, retrieved: list, top_k: int):
    return cross_encoder_rerank(query, retrieved, text_key="text")[:top_k]


async def _load_history(db: AsyncSession, conv_id: int, limit: int = 40) -> list[dict]:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(desc(Message.id))
            .limit(limit)
        )
    ).scalars().all()
    rows = list(reversed(rows))
    return [{"role": m.role, "content": m.content} for m in rows]


async def _load_recent_image_srcs(db: AsyncSession, conv_id: int, limit: int = 8) -> set[str]:
    rows = (
        await db.execute(
            select(Message.images)
            .where(
                Message.conversation_id == conv_id,
                Message.role == "assistant",
                Message.images.is_not(None),
            )
            .order_by(desc(Message.id))
            .limit(limit)
        )
    ).scalars().all()
    srcs: set[str] = set()
    for images in rows:
        for im in images or []:
            if isinstance(im, dict) and im.get("src"):
                srcs.add(str(im["src"]))
    return srcs


def _is_image_followup(query: str) -> bool:
    q = query or ""
    image_words = ("图", "图片", "照片", "相片", "配图", "画面")
    followup_words = ("其他", "别的", "更多", "还有", "再", "另外", "换", "有没有")
    return any(w in q for w in image_words) or any(w in q for w in followup_words)


def _wants_more_images(query: str) -> bool:
    q = query or ""
    return any(w in q for w in ("其他", "别的", "更多", "还有", "再来", "换一批", "另外"))


def _recent_academies(history: list[dict], limit: int = 8) -> list[str]:
    found: list[str] = []
    for msg in reversed(history[-limit:]):
        for name in detect_academies(msg.get("content") or ""):
            if name not in found:
                found.append(name)
        if found:
            break
    return found


def _contextual_rag_query(query: str, history: list[dict]) -> tuple[str, list[str]]:
    detected = detect_academies(query)
    if detected:
        # Add the canonical academy name as retrieval text when the user typed
        # a short alias such as "白鹿书院"; BM25 then sees "白鹿洞书院".
        prefix = " ".join(name for name in detected if name not in query)
        return (f"{prefix} {query}".strip() if prefix else query), detected

    recent = _recent_academies(history[:-1])
    if recent and _is_image_followup(query):
        return f"{' '.join(recent)} {query}", recent
    return query, []


async def _require_kb_read_all(
    db: AsyncSession,
    user: User,
    kb_ids: list[int],
) -> list[int]:
    """Validate chat-time KB selections before retrieval touches them."""
    deduped = list(dict.fromkeys(int(k) for k in kb_ids if k is not None))
    if not deduped:
        return []
    rows = (
        await db.execute(
            select(KnowledgeBase.id)
            .outerjoin(
                KBMember,
                and_(KBMember.kb_id == KnowledgeBase.id, KBMember.user_id == user.id),
            )
            .where(
                KnowledgeBase.id.in_(deduped),
                or_(
                    KnowledgeBase.owner_id == user.id,
                    KBMember.id.is_not(None),
                    KnowledgeBase.is_public.is_(True),
                ),
            )
        )
    ).scalars().all()
    allowed = set(rows)
    missing = [kb_id for kb_id in deduped if kb_id not in allowed]
    if missing:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"无权访问知识库: {missing}")
    return deduped


@router.post("/stream")
async def chat_stream(
    data: ChatSendIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    request_started = time.perf_counter()
    requested_kb_ids = data.kb_ids
    if not data.conversation_id and bool(data.rag_enabled) and requested_kb_ids:
        requested_kb_ids = await _require_kb_read_all(db, user, list(requested_kb_ids))

    # Resolve or create conversation
    conv: Conversation | None = None
    if data.conversation_id:
        conv = (
            await db.execute(
                select(Conversation).where(
                    Conversation.id == data.conversation_id,
                    Conversation.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if conv is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    else:
        conv = Conversation(
            user_id=user.id,
            title=data.message[:32] or "新对话",
            model=data.model or settings.default_chat_model,
            system_prompt=data.system_prompt or "",
            rag_enabled=bool(data.rag_enabled),
            kb_ids=requested_kb_ids,
            temperature=data.temperature if data.temperature is not None else 0.7,
            top_p=data.top_p if data.top_p is not None else 0.9,
            top_k=data.top_k or 6,
            rerank=(
                data.rerank
                if data.rerank is not None
                else settings.rerank_default_enabled
            ),
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

    # Apply per-request overrides
    model = data.model or conv.model
    temperature = data.temperature if data.temperature is not None else conv.temperature
    top_p = data.top_p if data.top_p is not None else conv.top_p
    system_prompt = data.system_prompt if data.system_prompt is not None else conv.system_prompt
    rag_enabled = bool(data.rag_enabled if data.rag_enabled is not None else conv.rag_enabled)
    kb_ids = requested_kb_ids if requested_kb_ids is not None else (conv.kb_ids or [])
    top_k = data.top_k if getattr(data, "top_k", None) else (conv.top_k or 6)
    rerank_on = bool(data.rerank if data.rerank is not None else conv.rerank)
    if rag_enabled and kb_ids:
        kb_ids = await _require_kb_read_all(db, user, list(kb_ids))

    # Think toggle — persisted inside the generic `params` JSON column to avoid
    # a schema migration. Explicit bool in the request wins and is saved;
    # otherwise fall back to whatever the conversation last used (None = model default).
    stored_think = None
    if isinstance(conv.params, dict):
        v = conv.params.get("think")
        if isinstance(v, bool):
            stored_think = v
    think: bool | None = data.think if data.think is not None else stored_think
    if data.think is not None and data.think != stored_think:
        params = dict(conv.params or {})
        params["think"] = bool(data.think)
        conv.params = params

    previous_model = conv.model
    conv.model = model
    conv.temperature = temperature
    conv.top_p = top_p
    conv.system_prompt = system_prompt or ""
    conv.rag_enabled = rag_enabled
    conv.kb_ids = list(kb_ids) if kb_ids else []
    conv.top_k = int(top_k)
    conv.rerank = rerank_on
    conv.updated_at = datetime.now()
    await db.commit()

    # If the user switched the conversation's model, best-effort unload the old
    # one so Ollama can free its weights rather than keep two models resident.
    # No-op for the MiMo cloud provider (nothing resident locally).
    if (
        settings.llm_provider.lower() == "ollama"
        and previous_model
        and previous_model != model
    ):
        asyncio.create_task(ollama.unload(previous_model))

    # Persist user message
    user_msg = Message(conversation_id=conv.id, role="user", content=data.message)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Load history up-front (uses this request's async session, which is closed after body returns).
    history = await _load_history(db, conv.id)
    rag_query, detected_academies = _contextual_rag_query(data.message, history)
    recent_image_srcs = await _load_recent_image_srcs(db, conv.id)
    exclude_recent_images = recent_image_srcs if _wants_more_images(data.message) else set()

    conv_id = conv.id
    conv_title_needs_update = conv.title in ("新对话", "") or conv.title == data.message[:32]

    async def event_gen():
        retrieval_ms: float | None = None
        rerank_ms: float | None = None
        gate_reason = "not_run"
        first_thinking_ms: float | None = None
        first_content_ms: float | None = None

        # Open the stream immediately so the client knows the request is live.
        yield _sse(
            "meta",
            {
                "conversation_id": conv_id,
                "user_message_id": user_msg.id,
                "model": model,
                "rag_enabled": rag_enabled,
                "kb_ids": list(kb_ids) if kb_ids else [],
            },
        )

        retrieved = []
        citations_out: list[dict] = []
        images_out: list[dict] = []
        effective_system = system_prompt or ""
        if rag_enabled and kb_ids and settings.rag_gate_enabled and not should_attempt_rag(rag_query):
            gate_reason = "query_not_rag_like"
            yield _sse("rag_skipped", {"reason": "query_not_rag_like"})
        elif rag_enabled and kb_ids:
            yield _sse("retrieving", {"kb_ids": list(kb_ids), "top_k": int(top_k)})
            retrieval_started = time.perf_counter()
            try:
                gate_before_rerank = settings.rag_gate_enabled and rerank_on
                retrieve_top_k = (
                    int(top_k) * settings.rerank_candidate_factor
                    if gate_before_rerank
                    else int(top_k)
                )
                retrieved = await asyncio.to_thread(
                    _run_retrieve,
                    list(kb_ids),
                    rag_query,
                    retrieve_top_k,
                    False if gate_before_rerank else rerank_on,
                )
                retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
                if settings.rag_gate_enabled:
                    decision = decide_rag_context(rag_query, retrieved)
                    gate_reason = decision.reason
                    log.info(
                        "rag_gate conv_id=%s use=%s reason=%s overlap=%.3f rrf=%.4f vector=%.4f qa=%.4f bm25=%.4f",
                        conv_id,
                        decision.use_context,
                        decision.reason,
                        decision.overlap,
                        decision.best_rrf,
                        decision.best_vector,
                        decision.best_qa,
                        decision.best_bm25,
                    )
                    if not decision.use_context:
                        retrieved = []
                        yield _sse(
                            "rag_skipped",
                            {
                                "reason": decision.reason,
                                "overlap": round(decision.overlap, 3),
                                "best_rrf": round(decision.best_rrf, 6),
                                "best_vector": round(decision.best_vector, 6),
                                "best_qa": round(decision.best_qa, 6),
                            },
                        )
                if retrieved:
                    if gate_before_rerank:
                        rerank_started = time.perf_counter()
                        retrieved = await asyncio.to_thread(
                            _run_rerank, rag_query, retrieved, int(top_k)
                        )
                        rerank_ms = (time.perf_counter() - rerank_started) * 1000
                    else:
                        retrieved = retrieved[: int(top_k)]
                    effective_system = build_rag_system_prompt(system_prompt, retrieved)
                    citations_out = citations_payload(retrieved, gate_reason=gate_reason)
                    images_out = collect_images(retrieved)
            except Exception as e:
                retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
                log.exception("retrieval failed: %s", e)
                yield _sse("warning", {"stage": "retrieval", "message": str(e)})

        msgs: list[dict] = []
        if effective_system:
            msgs.append({"role": "system", "content": effective_system})
        msgs.extend(history)

        # 自备书院图片：当问题点名某书院时，优先注入用户手工整理的高清图，
        # 与 PDF 抽取图去重合并（独立于 RAG 是否命中）。
        detected = detected_academies
        curated: list[dict] = []
        if detected:
            curated = images_for_academies(
                detected,
                settings.academy_images_dir,
                max_total=settings.rag_max_images,
                exclude_srcs=exclude_recent_images,
            )
            if curated:
                seen_src = {im.get("src") for im in images_out}
                images_out = (
                    [im for im in curated if im.get("src") not in seen_src] + images_out
                )[: settings.rag_max_images]
        log.debug(
            "image pipeline: detected=%s curated=%d images_out=%d",
            detected,
            len(curated),
            len(images_out),
        )

        if citations_out:
            yield _sse("citations", {"items": citations_out})
        if images_out:
            # 图文: hand the gallery to the frontend (web URLs) and prepare a
            # capped base64 subset for the multimodal model to actually see.
            yield _sse("images", {"items": images_out})

        llm_images = (
            _load_images_b64(images_out, settings.rag_max_images_to_llm)
            if images_out
            else None
        )

        full = ""
        try:
            async for delta in llm_chat_stream(
                model=model,
                messages=msgs,
                temperature=temperature,
                top_p=top_p,
                think=think,
                images=llm_images,
            ):
                if await request.is_disconnected():
                    break
                # Only surface reasoning when the user has thinking enabled.
                # MiMo may stream reasoning regardless of the request flag, so we
                # gate forwarding here to honour the UI toggle (think=False/None
                # hides the "thinking…" trace entirely).
                if "thinking" in delta and think:
                    if first_thinking_ms is None:
                        first_thinking_ms = (time.perf_counter() - request_started) * 1000
                    yield _sse("thinking", {"content": delta["thinking"]})
                if "content" in delta:
                    if first_content_ms is None:
                        first_content_ms = (time.perf_counter() - request_started) * 1000
                    full += delta["content"]
                    yield _sse("delta", {"content": delta["content"]})
                if delta.get("done"):
                    break
        except Exception as e:
            yield _sse("error", {"message": str(e)})
            full = full or f"[生成失败: {e}]"

        # Persist assistant message in a fresh session (this generator's db is closed after yield).
        async with SessionLocal() as s2:
            assistant_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=full,
                citations=citations_out or None,
                images=images_out or None,
            )
            s2.add(assistant_msg)
            if conv_title_needs_update:
                c = await s2.get(Conversation, conv_id)
                if c is not None:
                    c.title = (data.message[:32] or "新对话").strip()
                    c.updated_at = datetime.now()
            await s2.commit()
            await s2.refresh(assistant_msg)
            final_id = assistant_msg.id

        total_ms = (time.perf_counter() - request_started) * 1000
        log.info(
            "chat_stream timings conv_id=%s model=%s rag=%s kb_ids=%s retrieve_ms=%s gate_reason=%s rerank_ms=%s first_thinking_ms=%s first_token_ms=%s total_ms=%s citations_count=%s",
            conv_id,
            model,
            rag_enabled,
            list(kb_ids) if kb_ids else [],
            None if retrieval_ms is None else round(retrieval_ms, 1),
            gate_reason,
            None if rerank_ms is None else round(rerank_ms, 1),
            None if first_thinking_ms is None else round(first_thinking_ms, 1),
            None if first_content_ms is None else round(first_content_ms, 1),
            round(total_ms, 1),
            len(citations_out),
        )

        yield _sse("done", {"assistant_message_id": final_id})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
