"""Ollama embedding client (synchronous — used inside Celery workers)."""
import httpx

from app.core.config import settings

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            trust_env=False,
            timeout=httpx.Timeout(connect=10, read=300, write=30, pool=10),
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
        )
    return _client


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Batch-embed via Ollama /api/embed. Returns N x D vectors."""
    if not texts:
        return []
    model = model or settings.embed_model
    client = _get_client()
    r = client.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/embed",
        json={"model": model, "input": texts},
    )
    r.raise_for_status()
    data = r.json()
    vectors = data.get("embeddings") or []
    if not vectors and "embedding" in data:
        # Older Ollama single-input shape — fallback per-item
        vectors = [data["embedding"]]
    if len(vectors) != len(texts):
        # Some Ollama builds don't batch; fall back to per-item calls
        vectors = []
        for t in texts:
            rr = client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/embed",
                json={"model": model, "input": t},
            )
            rr.raise_for_status()
            d = rr.json()
            v = (d.get("embeddings") or [d.get("embedding")])[0]
            vectors.append(v)
    expected_dim = int(settings.embedding_dim or 0)
    if expected_dim:
        for idx, v in enumerate(vectors):
            if len(v) != expected_dim:
                raise RuntimeError(
                    f"Embedding dimension mismatch for model={model!r}: "
                    f"got {len(v)} dims at item {idx}, expected {expected_dim}. "
                    "Update EMBEDDING_DIM or use the configured embedding model."
                )
    return vectors


def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None
