"""Async Ollama HTTP client with a persistent httpx.AsyncClient.

Why persistent: creating a new AsyncClient per call re-does TCP + HTTP/1.1
keep-alive setup, which adds tens of ms under load. We keep one client alive
for the lifetime of the app (opened in lifespan, closed on shutdown).
Stream calls use a per-request timeout override because chat reads can take
minutes, but list/unload calls should fail fast.
"""
from collections.abc import AsyncIterator
import json
import httpx

from app.core.config import settings


class OllamaClient:
    """Thin async wrapper around the Ollama HTTP API."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # trust_env=False bypasses system proxies (e.g. VPN) for localhost calls
            self._client = httpx.AsyncClient(
                trust_env=False,
                timeout=httpx.Timeout(connect=10, read=None, write=30, pool=10),
                limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def list_models(self) -> list[dict]:
        client = self._ensure()
        r = await client.get(f"{self.base_url}/api/tags", timeout=10)
        r.raise_for_status()
        return r.json().get("models", [])

    async def warm(self, model: str) -> None:
        """Touch the model to trigger Ollama load. Best-effort, silent on failure."""
        try:
            client = self._ensure()
            await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": settings.ollama_keep_alive,
                },
                timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
            )
        except Exception:
            pass

    async def unload(self, model: str) -> None:
        """Ask Ollama to unload a specific model by setting keep_alive=0."""
        try:
            client = self._ensure()
            await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=10,
            )
        except Exception:
            pass

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        num_predict: int | None = None,
        think: bool | None = None,
    ) -> AsyncIterator[dict]:
        """Stream chat completion.

        Yields one of:
          - {'thinking': str}  — incremental reasoning chunk (qwen3 etc.)
          - {'content': str}   — incremental user-visible chunk
          - {'done': True}

        `think` — when False, disables the model's hidden reasoning trace
        (qwen3 and friends). Passed to Ollama's top-level ``think`` field.
        When None, Ollama's default applies.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "top_p": top_p},
            "keep_alive": settings.ollama_keep_alive,
        }
        if num_predict is not None:
            payload["options"]["num_predict"] = num_predict
        if think is not None:
            payload["think"] = bool(think)

        client = self._ensure()
        async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = data.get("message") or {}
                # Ollama 0.3+ returns thinking deltas in `message.thinking`.
                # Emit them so the UI can show "thinking…" progress instead
                # of a blank screen for reasoning models.
                tdelta = msg.get("thinking")
                if tdelta:
                    yield {"thinking": tdelta}
                cdelta = msg.get("content")
                if cdelta:
                    yield {"content": cdelta}
                if data.get("done"):
                    yield {"done": True}
                    break


ollama = OllamaClient()
