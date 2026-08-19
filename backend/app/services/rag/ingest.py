"""End-to-end ingest: PDF → text → chunks → embeddings → Qdrant + MySQL.

Runs inside a Celery worker. Uses synchronous SQLAlchemy session because Celery
tasks are synchronous and we want tight control over commits / progress.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from qdrant_client.http import models as qm
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.models.kb import KnowledgeBase
from app.services.chunker import chunk_pages
from app.services.mineru_parser import collect_page_images
from app.services.parser_dispatcher import parse_pdf
from app.services.rag.bm25_cache import invalidate as invalidate_bm25
from app.services.rag.embedder import embed_texts
from app.services.vector_store import ensure_collection, upsert_points

log = logging.getLogger(__name__)

PARSER_VERSION = "parser-v2-layout-table"
CHUNKER_VERSION = "chunker-v2-block-aware"


def _sync_engine():
    # Use pymysql (sync) for Celery; reuse the credentials
    uri = settings.alembic_database_uri
    return create_engine(uri, pool_pre_ping=True)


_engine = None
_SessionSync: sessionmaker | None = None


def _session() -> Session:
    global _engine, _SessionSync
    if _engine is None:
        _engine = _sync_engine()
        _SessionSync = sessionmaker(_engine, expire_on_commit=False)
    return _SessionSync()


def _update_status(
    db: Session,
    doc_id: int,
    status: DocumentStatus | None = None,
    progress: int | None = None,
    error: str | None = None,
    pages: int | None = None,
) -> None:
    doc = db.get(Document, doc_id)
    if doc is None:
        return
    if status is not None:
        doc.status = status
    if progress is not None:
        doc.progress = progress
    if error is not None:
        doc.error = error
    if pages is not None:
        doc.pages = pages
    db.commit()


def ingest_document(document_id: int) -> dict:
    """Full pipeline. Called from Celery task."""
    with _session() as db:
        doc = db.get(Document, document_id)
        if doc is None:
            return {"ok": False, "error": "document not found"}

        kb = db.get(KnowledgeBase, doc.kb_id)
        if kb is None:
            _update_status(db, document_id, status=DocumentStatus.failed, error="KB missing")
            return {"ok": False, "error": "kb not found"}

        try:
            # 1. Parse
            _update_status(db, document_id, status=DocumentStatus.parsing, progress=5)
            path = Path(doc.path)
            if not path.exists():
                raise FileNotFoundError(f"{path} missing")
            pages, total = parse_pdf(path)
            _update_status(db, document_id, progress=20, pages=total)

            # 2. Chunk
            _update_status(db, document_id, status=DocumentStatus.chunking, progress=25)
            pieces = chunk_pages(
                pages,
                chunk_size=kb.chunk_size,
                chunk_overlap=kb.chunk_overlap,
            )
            if not pieces:
                raise RuntimeError(
                    "未解析到任何可用文本。可能是扫描件 PDF，需等待 M6 的 OCR 回退。"
                )

            # Build a page -> images map from MinerU's content_list so each
            # chunk can carry figures on its page(s). This is decoupled from
            # text parsing: PDF_PARSER=legacy can still use MinerU figures.
            try:
                if (settings.pdf_image_extractor or "mineru").lower() == "mineru":
                    page_images = collect_page_images(path, ensure=True)
                else:
                    page_images = {}
            except Exception as e:
                log.warning("collect_page_images failed for doc %d: %s", doc.id, e)
                page_images = {}

            # Persist chunks to MySQL first (to mint FK ids)
            chunk_rows: list[Chunk] = []
            for p in pieces:
                meta: dict = {
                    "page_end": p.page_end,
                    "block_types": sorted(set(p.block_types)) if p.block_types else [],
                    "parser_version": PARSER_VERSION,
                    "chunker_version": CHUNKER_VERSION,
                }
                # M5: carry structured artefacts so the retriever/prompt layer
                # can restore full table/formula bodies at answer-time.
                if p.tables:
                    meta["tables"] = p.tables
                if p.formulas:
                    meta["formulas"] = p.formulas
                # Attach images across the chunk's page span (dedup by src).
                if page_images:
                    pages_span = range(p.page, (p.page_end or p.page) + 1)
                    imgs: list[dict] = []
                    seen_src: set[str] = set()
                    for pg in pages_span:
                        for im in page_images.get(pg, []):
                            src = im.get("src")
                            if not src or src in seen_src:
                                continue
                            seen_src.add(src)
                            imgs.append({"src": src, "page": pg, "caption": im.get("caption") or ""})
                    if imgs:
                        meta["images"] = imgs
                row = Chunk(
                    document_id=doc.id,
                    kb_id=doc.kb_id,
                    seq=p.seq,
                    text=p.text,
                    page=p.page,
                    token_count=p.char_count,  # char count as proxy until tokenizer is plugged
                    bbox=(p.bbox_ranges or None),
                    meta=meta,
                )
                db.add(row)
                chunk_rows.append(row)
            db.commit()
            for row in chunk_rows:
                db.refresh(row)
            _update_status(db, document_id, progress=40)

            total_chunks = len(chunk_rows)
            # 3. Embed in batches — skipped in the BM25-only (书院/MiMo) build,
            # which has no local embedding model. BM25 indexes from MySQL text.
            if settings.rag_vector_enabled:
                _update_status(db, document_id, status=DocumentStatus.embedding, progress=45)
                collection = ensure_collection(kb.id)
                batch_size = 32
                done = 0
                for i in range(0, total_chunks, batch_size):
                    batch = chunk_rows[i : i + batch_size]
                    vectors = embed_texts([c.text for c in batch], model=kb.embedding_model)
                    points: list[qm.PointStruct] = []
                    for c, v in zip(batch, vectors):
                        pid = str(uuid.uuid4())
                        c.qdrant_point_id = pid
                        points.append(
                            qm.PointStruct(
                                id=pid,
                                vector=v,
                                payload={
                                    "kb_id": c.kb_id,
                                    "document_id": c.document_id,
                                    "chunk_id": c.id,
                                    "type": "chunk",
                                    "page": c.page,
                                    "seq": c.seq,
                                    "filename": doc.filename,
                                    "text": c.text[:500],
                                },
                            )
                        )
                    upsert_points(collection, points)
                    db.commit()
                    done += len(batch)
                    pct = 45 + int(50 * done / max(total_chunks, 1))
                    _update_status(db, document_id, progress=min(pct, 95))

            _update_status(db, document_id, status=DocumentStatus.done, progress=100, error=None)
            # BM25 cache must be rebuilt next time the retriever queries this KB
            invalidate_bm25(doc.kb_id)

            # Optional QA enrichment is intentionally off by default because it
            # competes with chat models and can be triggered manually from UI/API.
            if kb.qa_enabled and settings.qa_auto_generate_on_ingest:
                try:
                    from app.workers.tasks import generate_qa_for_document_task

                    generate_qa_for_document_task.delay(doc.id)
                except Exception as e:
                    log.warning("failed to enqueue QA task for doc %d: %s", doc.id, e)

            log.info(
                "ingest complete doc_id=%s kb_id=%s pages=%s chunks=%s parser_version=%s chunker_version=%s qa_auto=%s",
                doc.id,
                doc.kb_id,
                total,
                total_chunks,
                PARSER_VERSION,
                CHUNKER_VERSION,
                bool(kb.qa_enabled and settings.qa_auto_generate_on_ingest),
            )
            return {"ok": True, "chunks": total_chunks}
        except Exception as e:
            log.exception("ingest failed")
            _update_status(db, document_id, status=DocumentStatus.failed, error=str(e))
            return {"ok": False, "error": str(e)}


def reembed_kb(kb_id: int) -> dict:
    """Re-run embedding for all docs already chunked in a KB (future utility)."""
    with _session() as db:
        docs = db.execute(select(Document).where(Document.kb_id == kb_id)).scalars().all()
        for d in docs:
            ingest_document(d.id)
    return {"ok": True}
