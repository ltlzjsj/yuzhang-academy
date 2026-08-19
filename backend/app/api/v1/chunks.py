from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.kb import KBMember, KnowledgeBase
from app.models.user import User
from app.schemas.kb import ChunkOut

router = APIRouter(prefix="/chunks", tags=["chunks"])


async def _check_read(db: AsyncSession, user: User, kb_id: int) -> None:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(404, "知识库不存在")
    if kb.owner_id == user.id:
        return
    member = (
        await db.execute(
            select(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if member is None:
        raise HTTPException(403, "无权访问")


@router.get("", response_model=dict)
async def list_chunks(
    document_id: int = Query(...),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (await db.execute(select(Document).where(Document.id == document_id))).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_read(db, user, doc.kb_id)

    total = (
        await db.execute(
            select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.seq.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    items = []
    for c in rows:
        items.append(
            ChunkOut(
                id=c.id,
                document_id=c.document_id,
                kb_id=c.kb_id,
                seq=c.seq,
                text=c.text,
                page=c.page,
                token_count=c.token_count,
                bbox=c.bbox,
                metadata=c.meta,
            )
        )

    return {"total": int(total or 0), "items": items, "page": page, "size": size}
