"""Stateless persona-agent chat (历史名人对话 / 首页数字人导览).

Deliberately separate from `/chat/stream`: it persists nothing, so these guided
persona conversations never pollute the user's main conversation history. It
still reuses the same retrieval + LLM building blocks for grounded answers.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, create_engine, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.kb import KBMember, KnowledgeBase
from app.models.user import User
from app.schemas.agent import AgentChatIn
from app.services.llm import chat_stream as llm_chat_stream
from app.services.rag.context import build_rag_system_prompt, citations_payload
from app.services.rag.gate import decide_rag_context, should_attempt_rag
from app.services.rag.retriever import retrieve

log = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

_sync_engine = None
_SyncSession: sessionmaker | None = None


def _get_sync_session() -> Session:
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(settings.alembic_database_uri, pool_pre_ping=True)
        _SyncSession = sessionmaker(_sync_engine, expire_on_commit=False)
    return _SyncSession()


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _run_retrieve(kb_ids: list[int], query: str, top_k: int):
    with _get_sync_session() as db:
        return retrieve(db, kb_ids, query, top_k=top_k, rerank=False)


async def _allowed_kb_ids(db: AsyncSession, user: User, kb_ids: list[int]) -> list[int]:
    ids = list(dict.fromkeys(int(k) for k in kb_ids if k is not None))
    if not ids:
        return []
    rows = (
        await db.execute(
            select(KnowledgeBase.id)
            .outerjoin(KBMember, and_(KBMember.kb_id == KnowledgeBase.id, KBMember.user_id == user.id))
            .where(
                KnowledgeBase.id.in_(ids),
                or_(
                    KnowledgeBase.owner_id == user.id,
                    KBMember.id.is_not(None),
                    KnowledgeBase.is_public.is_(True),
                ),
            )
        )
    ).scalars().all()
    allowed = set(rows)
    # Silently drop KBs the user can't read — agents shouldn't hard-fail the chat.
    return [kb_id for kb_id in ids if kb_id in allowed]


@router.post("/stream")
async def agent_stream(
    data: AgentChatIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    history = [
        {"role": m.role, "content": m.content}
        for m in data.messages
        if m.role in ("user", "assistant") and m.content
    ]
    last_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    kb_ids = await _allowed_kb_ids(db, user, data.kb_ids) if data.rag_enabled else []
    temperature = data.temperature if data.temperature is not None else 0.7
    top_p = data.top_p if data.top_p is not None else 0.9

    async def event_gen():
        effective_system = (data.system_prompt or "").strip()
        citations_out: list[dict] = []

        if kb_ids and last_user:
            do_rag = (not settings.rag_gate_enabled) or should_attempt_rag(last_user)
            if do_rag:
                yield _sse("retrieving", {"kb_ids": kb_ids})
                try:
                    retrieved = await asyncio.to_thread(_run_retrieve, kb_ids, last_user, 6)
                    if settings.rag_gate_enabled:
                        decision = decide_rag_context(last_user, retrieved)
                        if not decision.use_context:
                            retrieved = []
                    if retrieved:
                        effective_system = build_rag_system_prompt(
                            effective_system,
                            retrieved,
                            include_image_instruction=False,
                        )
                        citations_out = citations_payload(retrieved)
                except Exception as e:  # noqa: BLE001
                    log.warning("agent retrieval failed: %s", e)

        if citations_out:
            yield _sse("citations", {"items": citations_out})

        msgs: list[dict] = []
        if effective_system:
            msgs.append({"role": "system", "content": effective_system})
        msgs.extend(history)

        try:
            async for delta in llm_chat_stream(
                model=settings.default_chat_model,
                messages=msgs,
                temperature=temperature,
                top_p=top_p,
                think=False,
            ):
                if await request.is_disconnected():
                    break
                if "content" in delta:
                    yield _sse("delta", {"content": delta["content"]})
                if delta.get("done"):
                    break
        except Exception as e:  # noqa: BLE001
            yield _sse("error", {"message": str(e)})

        yield _sse("done", {})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
