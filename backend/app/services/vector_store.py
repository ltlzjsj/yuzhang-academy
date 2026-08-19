from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import settings

# bge-m3 embedding dimension by default. Kept configurable so a mismatched
# embedding model fails clearly instead of surfacing as opaque Qdrant errors.
EMBED_DIM = settings.embedding_dim


@lru_cache(maxsize=1)
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def close_client() -> None:
    client = get_client()
    close = getattr(client, "close", None)
    if callable(close):
        close()
    get_client.cache_clear()


def collection_name_for_kb(kb_id: int) -> str:
    return f"kb_{kb_id}"


def ensure_collection(kb_id: int) -> str:
    """Create the collection for a KB if missing. Returns its name."""
    client = get_client()
    name = collection_name_for_kb(kb_id)
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=EMBED_DIM, distance=qm.Distance.COSINE),
        )
        # Payload index for fast filtering
        for field in ("kb_id", "document_id", "chunk_id", "type"):
            try:
                client.create_payload_index(
                    collection_name=name,
                    field_name=field,
                    field_schema=qm.PayloadSchemaType.INTEGER
                    if field != "type"
                    else qm.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                pass
    return name


def drop_collection(kb_id: int) -> None:
    client = get_client()
    name = collection_name_for_kb(kb_id)
    try:
        client.delete_collection(collection_name=name)
    except Exception:
        pass


def upsert_points(
    collection: str,
    points: list[qm.PointStruct],
) -> None:
    if not points:
        return
    get_client().upsert(collection_name=collection, points=points, wait=True)


def search_points(
    collection: str,
    vector: list[float],
    limit: int = 20,
    type_filter: str = "chunk",
) -> list[dict]:
    """Vector-similarity search inside one KB collection.

    Returns a list of plain dicts with keys: chunk_id, document_id, page,
    filename, text_preview, score. If the collection doesn't exist, returns [].
    """
    client = get_client()
    flt = qm.Filter(
        must=[qm.FieldCondition(key="type", match=qm.MatchValue(value=type_filter))]
    )
    try:
        hits = client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
    except Exception:
        return []
    out: list[dict] = []
    for h in hits:
        p = h.payload or {}
        out.append(
            {
                "chunk_id": int(p.get("chunk_id")) if p.get("chunk_id") is not None else None,
                "document_id": p.get("document_id"),
                "page": p.get("page"),
                "filename": p.get("filename"),
                "text_preview": p.get("text"),
                "score": float(h.score),
            }
        )
    return out


def delete_by_document(collection: str, document_id: int) -> None:
    """Remove both chunk- and QA-typed points for a document."""
    client = get_client()
    client.delete(
        collection_name=collection,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
            )
        ),
        wait=True,
    )


def search_qa_points(
    collection: str,
    vector: list[float],
    limit: int = 20,
) -> list[dict]:
    """Vector search over the QA channel (``type="qa"``).

    Returns dicts with ``chunk_id`` (link back to source chunk), ``qa_id``,
    ``question``, ``answer``, ``score``. Returns [] if collection missing.
    """
    client = get_client()
    flt = qm.Filter(must=[qm.FieldCondition(key="type", match=qm.MatchValue(value="qa"))])
    try:
        hits = client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
    except Exception:
        return []
    out: list[dict] = []
    for h in hits:
        p = h.payload or {}
        cid = p.get("chunk_id")
        if cid is None:
            continue
        out.append(
            {
                "chunk_id": int(cid),
                "qa_id": p.get("qa_id"),
                "question": p.get("question"),
                "answer": p.get("answer"),
                "score": float(h.score),
            }
        )
    return out
