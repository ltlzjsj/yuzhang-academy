"""QA pair browse + manual curation endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from qdrant_client.http import models as qm
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.chunk import Chunk, QAPair
from app.models.document import Document
from app.models.kb import KBMember, KBPermission, KnowledgeBase
from app.models.user import User
from app.services.vector_store import collection_name_for_kb, get_client

router = APIRouter(prefix="/qa", tags=["qa"])


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


async def _check_write(db: AsyncSession, user: User, kb_id: int) -> KnowledgeBase:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(404, "知识库不存在")
    if kb.owner_id == user.id:
        return kb
    member = (
        await db.execute(
            select(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if member is None or member.permission == KBPermission.read:
        raise HTTPException(403, "无写入权限")
    return kb


@router.get("", response_model=dict)
async def list_qa(
    kb_id: int = Query(...),
    document_id: int | None = Query(None),
    q: str | None = Query(None, description="子串匹配问题或答案"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Paginated QA pairs for a KB, optionally filtered by document / keyword.

    Each row is joined with its source chunk to expose ``page`` + ``document_id``
    so the frontend can link back into the citation drawer.
    """
    await _check_read(db, user, kb_id)

    base = (
        select(QAPair, Chunk.page, Chunk.document_id, Document.filename)
        .join(Chunk, Chunk.id == QAPair.chunk_id)
        .join(Document, Document.id == Chunk.document_id)
        .where(QAPair.kb_id == kb_id)
    )
    count_q = select(func.count(QAPair.id)).where(QAPair.kb_id == kb_id)

    if document_id is not None:
        base = base.where(Chunk.document_id == document_id)
        count_q = count_q.join(Chunk, Chunk.id == QAPair.chunk_id).where(
            Chunk.document_id == document_id
        )
    if q:
        pat = f"%{q}%"
        base = base.where((QAPair.question.ilike(pat)) | (QAPair.answer.ilike(pat)))
        # Counting with same filter — simpler to just count ids in a subquery
        count_q = select(func.count(QAPair.id)).where(
            QAPair.kb_id == kb_id,
            (QAPair.question.ilike(pat)) | (QAPair.answer.ilike(pat)),
        )
        if document_id is not None:
            count_q = count_q.join(Chunk, Chunk.id == QAPair.chunk_id).where(
                Chunk.document_id == document_id
            )

    total = (await db.execute(count_q)).scalar_one()
    rows = (
        await db.execute(
            base.order_by(desc(QAPair.id)).offset((page - 1) * size).limit(size)
        )
    ).all()

    items = []
    for qa, pg, doc_id, fname in rows:
        items.append(
            {
                "id": qa.id,
                "chunk_id": qa.chunk_id,
                "kb_id": qa.kb_id,
                "document_id": doc_id,
                "filename": fname,
                "page": pg,
                "question": qa.question,
                "answer": qa.answer,
                "created_at": qa.created_at.isoformat() if qa.created_at else None,
            }
        )
    return {"total": int(total or 0), "items": items, "page": page, "size": size}


@router.delete("/{qa_id}", status_code=204)
async def delete_qa(
    qa_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a bad QA pair (DB row + Qdrant point)."""
    row = (
        await db.execute(select(QAPair).where(QAPair.id == qa_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "QA 不存在")
    await _check_write(db, user, row.kb_id)

    # Nuke Qdrant point if we know its id (defensive: also filter by qa_id
    # payload so older rows without qdrant_point_id still get cleaned).
    try:
        collection = collection_name_for_kb(row.kb_id)
        if row.qdrant_point_id:
            get_client().delete(
                collection_name=collection,
                points_selector=qm.PointIdsList(points=[row.qdrant_point_id]),
                wait=True,
            )
        else:
            get_client().delete(
                collection_name=collection,
                points_selector=qm.FilterSelector(
                    filter=qm.Filter(
                        must=[
                            qm.FieldCondition(
                                key="type", match=qm.MatchValue(value="qa")
                            ),
                            qm.FieldCondition(
                                key="qa_id", match=qm.MatchValue(value=row.id)
                            ),
                        ]
                    )
                ),
                wait=True,
            )
    except Exception:
        # Orphan vector is tolerable — retriever will just surface a dead chunk_id
        # which gets hydrated out during the join.
        pass

    await db.delete(row)
    await db.commit()
