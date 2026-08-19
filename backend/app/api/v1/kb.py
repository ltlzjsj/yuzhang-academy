from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, is_admin, require_admin
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.kb import KBMember, KBPermission, KnowledgeBase
from app.models.user import User
from app.schemas.kb import KBCreate, KBOut, KBUpdate
from app.services.vector_store import (
    collection_name_for_kb,
    drop_collection,
    ensure_collection,
)

router = APIRouter(prefix="/kb", tags=["knowledge-bases"])


async def _load_kb(db: AsyncSession, user: User, kb_id: int, *, write: bool = False) -> KnowledgeBase:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库不存在")
    # Owner / 管理员 shortcut（管理员可管理任意知识库）
    if kb.owner_id == user.id or is_admin(user):
        return kb
    # Otherwise membership
    member = (
        await db.execute(
            select(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if member is None:
        # 公开 KB 允许任何登录用户「读」（供公开官网 AI 使用）；写仍需所有者/成员。
        if not write and kb.is_public:
            return kb
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该知识库")
    if write and member.permission == KBPermission.read:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无写入权限")
    return kb


async def _kb_out(db: AsyncSession, kb: KnowledgeBase) -> KBOut:
    doc_count = (
        await db.execute(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        )
    ).scalar_one()
    chunk_count = (
        await db.execute(
            select(func.count(Chunk.id)).where(Chunk.kb_id == kb.id)
        )
    ).scalar_one()
    data = KBOut.model_validate(kb)
    data.document_count = int(doc_count or 0)
    data.chunk_count = int(chunk_count or 0)
    return data


@router.get("", response_model=list[KBOut])
async def list_kbs(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    doc_counts = (
        select(Document.kb_id, func.count(Document.id).label("document_count"))
        .group_by(Document.kb_id)
        .subquery()
    )
    chunk_counts = (
        select(Chunk.kb_id, func.count(Chunk.id).label("chunk_count"))
        .group_by(Chunk.kb_id)
        .subquery()
    )
    stmt = (
        select(
            KnowledgeBase,
            func.coalesce(doc_counts.c.document_count, 0),
            func.coalesce(chunk_counts.c.chunk_count, 0),
        )
        .outerjoin(doc_counts, doc_counts.c.kb_id == KnowledgeBase.id)
        .outerjoin(chunk_counts, chunk_counts.c.kb_id == KnowledgeBase.id)
        .order_by(desc(KnowledgeBase.created_at))
    )
    # 管理员看全部知识库；普通用户看 自己的 + 加入的 + 公开的。
    if not is_admin(user):
        owned = select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user.id)
        joined = select(KBMember.kb_id).where(KBMember.user_id == user.id)
        public = select(KnowledgeBase.id).where(KnowledgeBase.is_public.is_(True))
        stmt = stmt.where(KnowledgeBase.id.in_(owned.union(joined, public)))
    rows = (await db.execute(stmt)).all()
    out: list[KBOut] = []
    for kb, doc_count, chunk_count in rows:
        data = KBOut.model_validate(kb)
        data.document_count = int(doc_count or 0)
        data.chunk_count = int(chunk_count or 0)
        out.append(data)
    return out


@router.post("", response_model=KBOut, status_code=201)
async def create_kb(
    data: KBCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    kb = KnowledgeBase(
        name=data.name,
        description=data.description,
        owner_id=user.id,
        chunk_size=data.chunk_size,
        chunk_overlap=data.chunk_overlap,
        qa_enabled=data.qa_enabled,
        qa_model=data.qa_model,
        qa_pairs_per_chunk=data.qa_pairs_per_chunk,
        qdrant_collection="",  # filled after flush
    )
    db.add(kb)
    await db.flush()
    kb.qdrant_collection = collection_name_for_kb(kb.id)
    # Seed owner as a member for consistency
    db.add(KBMember(kb_id=kb.id, user_id=user.id, permission=KBPermission.owner))
    await db.commit()
    await db.refresh(kb)
    # Create Qdrant collection
    try:
        ensure_collection(kb.id)
    except Exception as e:
        raise HTTPException(500, f"创建 Qdrant collection 失败: {e}")
    return await _kb_out(db, kb)


@router.get("/{kb_id}", response_model=KBOut)
async def get_kb(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    kb = await _load_kb(db, user, kb_id)
    return await _kb_out(db, kb)


@router.patch("/{kb_id}", response_model=KBOut)
async def update_kb(
    kb_id: int,
    data: KBUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    kb = await _load_kb(db, user, kb_id, write=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(kb, field, value)
    await db.commit()
    await db.refresh(kb)
    return await _kb_out(db, kb)


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    kb = await _load_kb(db, user, kb_id, write=True)
    if kb.owner_id != user.id and not is_admin(user):
        raise HTTPException(403, "只有所有者或管理员可以删除知识库")
    await db.delete(kb)
    await db.commit()
    drop_collection(kb_id)


@router.post("/{kb_id}/qa/generate", status_code=202)
async def generate_qa_for_kb(
    kb_id: int,
    model: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Kick off async QA-pair generation across every document in the KB.

    Optional `model` query param overrides `kb.qa_model` for this run only
    (not persisted). Returns 202 immediately; progress surfaces via `/qa/stats`.
    Requires ``qa_enabled=True`` on the KB — flip via PATCH /kb/{id} first.
    """
    kb = await _load_kb(db, user, kb_id, write=True)
    if not kb.qa_enabled:
        raise HTTPException(400, "该知识库未启用 QA 生成 (qa_enabled=false)")
    try:
        from app.workers.tasks import generate_qa_for_kb_task

        generate_qa_for_kb_task.delay(kb.id, (model or None))
    except Exception as e:
        raise HTTPException(500, f"无法启动 QA 任务: {e}")
    return {"ok": True, "kb_id": kb.id, "model": model or kb.qa_model, "message": "QA 生成已入队"}


@router.get("/{kb_id}/qa/stats")
async def qa_stats(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lightweight QA coverage report: pair count + distinct chunks with QA."""
    await _load_kb(db, user, kb_id)
    from app.models.chunk import QAPair

    pair_count = (
        await db.execute(select(func.count(QAPair.id)).where(QAPair.kb_id == kb_id))
    ).scalar_one()
    covered_chunks = (
        await db.execute(
            select(func.count(func.distinct(QAPair.chunk_id))).where(
                QAPair.kb_id == kb_id
            )
        )
    ).scalar_one()
    total_chunks = (
        await db.execute(select(func.count(Chunk.id)).where(Chunk.kb_id == kb_id))
    ).scalar_one()
    return {
        "kb_id": kb_id,
        "pairs": int(pair_count or 0),
        "covered_chunks": int(covered_chunks or 0),
        "total_chunks": int(total_chunks or 0),
    }
