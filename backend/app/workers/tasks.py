from app.workers.celery_app import celery_app
from app.services.rag.ingest import ingest_document as _ingest_document
from app.services.rag.qa_gen import (
    generate_qa_for_document as _gen_qa_doc,
    generate_qa_for_kb as _gen_qa_kb,
)


@celery_app.task(name="georag.ingest_document")
def ingest_document_task(document_id: int) -> dict:
    return _ingest_document(document_id)


@celery_app.task(name="georag.generate_qa_for_document")
def generate_qa_for_document_task(document_id: int, model_override: str | None = None) -> dict:
    return _gen_qa_doc(document_id, model_override=model_override)


@celery_app.task(name="georag.generate_qa_for_kb")
def generate_qa_for_kb_task(kb_id: int, model_override: str | None = None) -> dict:
    return _gen_qa_kb(kb_id, model_override=model_override)
