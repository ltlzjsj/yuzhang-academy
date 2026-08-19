import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import (
    _load_kb_and_member,
    get_current_user,
    require_kb_read,
    require_kb_write,
)
from app.models.document import Document, DocumentStatus
from app.models.chunk import Chunk, QAPair
from app.models.kb import KBPermission, KnowledgeBase
from app.models.user import User
from app.schemas.kb import DocumentMetadataUpdate, DocumentOut
from app.services.rag.bm25_cache import invalidate as invalidate_bm25
from app.services.vector_store import delete_by_document, collection_name_for_kb

router = APIRouter(prefix="/documents", tags=["documents"])

# Upload constraints. PDF-only today; cap size to avoid runaway disk/ingest cost.
_ALLOWED_EXT = {".pdf"}
_MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
_PDF_MAGIC = b"%PDF"


def _doc_out(
    doc: Document,
    *,
    image_count: int = 0,
    image_preview: list[dict] | None = None,
) -> DocumentOut:
    data = DocumentOut.model_validate(doc)
    data.image_count = int(image_count or 0)
    data.image_preview = image_preview or []
    return data


async def _image_summaries(
    db: AsyncSession,
    doc_ids: list[int],
    *,
    preview_limit: int = 4,
) -> dict[int, dict]:
    if not doc_ids:
        return {}
    rows = (
        await db.execute(
            select(Chunk.document_id, Chunk.meta).where(Chunk.document_id.in_(doc_ids))
        )
    ).all()
    out: dict[int, dict] = {
        doc_id: {"image_count": 0, "image_preview": [], "_seen": set()} for doc_id in doc_ids
    }
    for doc_id, meta in rows:
        if not isinstance(meta, dict):
            continue
        images = meta.get("images")
        if not isinstance(images, list):
            continue
        bucket = out.setdefault(doc_id, {"image_count": 0, "image_preview": [], "_seen": set()})
        seen: set = bucket["_seen"]
        for im in images:
            if not isinstance(im, dict):
                continue
            src = im.get("src")
            if not src or src in seen:
                continue
            seen.add(src)
            bucket["image_count"] += 1
            if len(bucket["image_preview"]) < preview_limit:
                bucket["image_preview"].append(
                    {
                        "src": src,
                        "page": im.get("page"),
                        "caption": im.get("caption") or "",
                        "kind": im.get("kind") or "mineru",
                    }
                )
    for value in out.values():
        value.pop("_seen", None)
    return out


async def _check_doc_read(db: AsyncSession, user: User, doc: Document) -> None:
    kb, member = await _load_kb_and_member(db, user, doc.kb_id)
    if kb.owner_id != user.id and member is None:
        raise HTTPException(403, "无权访问")


async def _check_doc_write(db: AsyncSession, user: User, doc: Document) -> KnowledgeBase:
    kb, member = await _load_kb_and_member(db, user, doc.kb_id)
    if kb.owner_id == user.id:
        return kb
    if member is None or member.permission == KBPermission.read:
        raise HTTPException(403, "无上传权限")
    return kb


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    kb: KnowledgeBase = Depends(require_kb_read),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Document).where(Document.kb_id == kb.id).order_by(desc(Document.created_at))
        )
    ).scalars().all()
    summaries = await _image_summaries(db, [doc.id for doc in rows])
    return [
        _doc_out(
            doc,
            image_count=summaries.get(doc.id, {}).get("image_count", 0),
            image_preview=summaries.get(doc.id, {}).get("image_preview", []),
        )
        for doc in rows
    ]


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    kb: KnowledgeBase = Depends(require_kb_write),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Strict extension whitelist. Even though we generate the on-disk name from
    # a uuid (so user input can't break out of upload_dir), we still only let
    # through file types we can actually ingest.
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, "目前仅支持 PDF 文件")

    # Save to upload dir
    upload_root = Path(settings.upload_dir) / f"kb_{kb.id}"
    upload_root.mkdir(parents=True, exist_ok=True)
    disk_name = f"{uuid.uuid4().hex}{ext}"
    disk_path = upload_root / disk_name

    total = 0
    seen_header = False
    with disk_path.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            if not seen_header:
                seen_header = True
                if not chunk.lstrip().startswith(_PDF_MAGIC):
                    f.close()
                    disk_path.unlink(missing_ok=True)
                    raise HTTPException(400, "上传文件不是有效 PDF")
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                f.close()
                disk_path.unlink(missing_ok=True)
                raise HTTPException(413, f"文件超过上限 {_MAX_UPLOAD_BYTES // (1024*1024)}MB")
            f.write(chunk)

    doc = Document(
        kb_id=kb.id,
        filename=file.filename,
        path=str(disk_path),
        size_bytes=total,
        status=DocumentStatus.pending,
        progress=0,
        uploader_id=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Enqueue Celery task (lazy import so API boot doesn't need broker up)
    try:
        from app.workers.tasks import ingest_document_task

        ingest_document_task.delay(doc.id)
    except Exception as e:
        doc.status = DocumentStatus.failed
        doc.error = f"无法入队: {e}"
        await db.commit()
        raise HTTPException(500, f"无法启动后台任务: {e}")

    return _doc_out(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_doc_read(db, user, doc)
    summaries = await _image_summaries(db, [doc.id])
    return _doc_out(
        doc,
        image_count=summaries.get(doc.id, {}).get("image_count", 0),
        image_preview=summaries.get(doc.id, {}).get("image_preview", []),
    )


@router.patch("/{doc_id}/metadata", response_model=DocumentOut)
async def update_document_metadata(
    doc_id: int,
    data: DocumentMetadataUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_doc_write(db, user, doc)

    cleaned: dict[str, str | int | float | bool | None] = {}
    for raw_key, value in (data.metadata or {}).items():
        key = str(raw_key).strip()
        if not key:
            continue
        if len(key) > 64:
            raise HTTPException(400, "metadata 字段名不能超过 64 个字符")
        if isinstance(value, str) and len(value) > 512:
            raise HTTPException(400, f"metadata 字段 {key} 的值不能超过 512 个字符")
        cleaned[key] = value
    if len(cleaned) > 50:
        raise HTTPException(400, "metadata 字段数量不能超过 50 个")

    doc.meta = cleaned
    await db.commit()
    await db.refresh(doc)
    summaries = await _image_summaries(db, [doc.id])
    return _doc_out(
        doc,
        image_count=summaries.get(doc.id, {}).get("image_count", 0),
        image_preview=summaries.get(doc.id, {}).get("image_preview", []),
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_doc_write(db, user, doc)

    # Remove vectors only when vector retrieval is enabled. Cloud deployments
    # can run BM25-only with no Qdrant service.
    if settings.rag_vector_enabled:
        delete_by_document(collection_name_for_kb(doc.kb_id), doc.id)

    # Remove file
    try:
        Path(doc.path).unlink(missing_ok=True)
    except Exception:
        pass

    kb_id = doc.kb_id
    await db.delete(doc)
    await db.commit()
    invalidate_bm25(kb_id)


@router.get("/{doc_id}/file")
async def download_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream the original PDF back for in-browser rendering (citation drawer).

    Auth is enforced here; the frontend must include the bearer token. That
    means we can't use a plain <iframe src> — PDF.js loads the bytes via fetch
    with the Authorization header, which is what we want anyway.
    """
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    # Read-access check
    await _check_doc_read(db, user, doc)

    path = Path(doc.path)
    if not path.exists():
        raise HTTPException(404, "文件已丢失")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=doc.filename,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{doc_id}/qa/stats")
async def document_qa_stats(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_doc_read(db, user, doc)

    pair_count = (
        await db.execute(
            select(func.count(QAPair.id))
            .join(Chunk, Chunk.id == QAPair.chunk_id)
            .where(Chunk.document_id == doc.id)
        )
    ).scalar_one()
    covered_chunks = (
        await db.execute(
            select(func.count(func.distinct(QAPair.chunk_id)))
            .join(Chunk, Chunk.id == QAPair.chunk_id)
            .where(Chunk.document_id == doc.id)
        )
    ).scalar_one()
    total_chunks = (
        await db.execute(select(func.count(Chunk.id)).where(Chunk.document_id == doc.id))
    ).scalar_one()
    return {
        "document_id": doc.id,
        "kb_id": doc.kb_id,
        "pairs": int(pair_count or 0),
        "covered_chunks": int(covered_chunks or 0),
        "total_chunks": int(total_chunks or 0),
    }


@router.post("/{doc_id}/qa/generate", status_code=202)
async def generate_qa_for_doc(
    doc_id: int,
    model: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Regenerate QA pairs for a single document. Wipes existing ones first.

    Optional `model` query param overrides `kb.qa_model` for this run only.
    """
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    kb = await _check_doc_write(db, user, doc)
    if not kb.qa_enabled:
        raise HTTPException(400, "该知识库未启用 QA 生成 (qa_enabled=false)")
    try:
        from app.workers.tasks import generate_qa_for_document_task

        generate_qa_for_document_task.delay(doc.id, (model or None))
    except Exception as e:
        raise HTTPException(500, f"无法启动 QA 任务: {e}")
    return {"ok": True, "document_id": doc.id, "model": model or kb.qa_model, "message": "QA 生成已入队"}


@router.post("/{doc_id}/reingest", response_model=DocumentOut)
async def reingest_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "文档不存在")
    await _check_doc_write(db, user, doc)

    # Clear old chunks + vectors. Skip Qdrant in BM25-only deployments.
    if settings.rag_vector_enabled:
        delete_by_document(collection_name_for_kb(doc.kb_id), doc.id)
    from app.models.chunk import Chunk
    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(Chunk).where(Chunk.document_id == doc.id))
    doc.status = DocumentStatus.pending
    doc.progress = 0
    doc.error = None
    await db.commit()
    await db.refresh(doc)
    invalidate_bm25(doc.kb_id)

    from app.workers.tasks import ingest_document_task

    ingest_document_task.delay(doc.id)
    return _doc_out(doc)
