from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_owned(db: AsyncSession, user: User, conv_id: int) -> Conversation:
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id, Conversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(desc(Conversation.updated_at))
        )
    ).scalars().all()
    return rows


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = Conversation(
        user_id=user.id,
        title=data.title or "新对话",
        model=data.model or settings.default_chat_model,
        system_prompt=data.system_prompt,
        rag_enabled=data.rag_enabled,
        kb_ids=data.kb_ids,
        temperature=data.temperature,
        top_p=data.top_p,
        top_k=data.top_k,
        rerank=data.rerank if data.rerank is not None else settings.rerank_default_enabled,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/{conv_id}", response_model=ConversationOut)
async def get_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_owned(db, user, conv_id)


@router.patch("/{conv_id}", response_model=ConversationOut)
async def update_conversation(
    conv_id: int,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await _get_owned(db, user, conv_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(conv, field, value)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv = await _get_owned(db, user, conv_id)
    await db.delete(conv)
    await db.commit()


@router.get("/{conv_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conv_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_owned(db, user, conv_id)
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.id.asc())
        )
    ).scalars().all()
    return rows


@router.delete("/{conv_id}/messages/{message_id}/tail", status_code=204)
async def delete_message_tail(
    conv_id: int,
    message_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _get_owned(db, user, conv_id)
    msg = (
        await db.execute(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conv_id,
            )
        )
    ).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "消息不存在")
    await db.execute(
        sa_delete(Message).where(
            Message.conversation_id == conv_id,
            Message.id >= msg.id,
        )
    )
    await db.commit()
