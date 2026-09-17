"""Async client for Xiaomi MiMo's Anthropic-compatible Messages API.

MiMo (小米 MiMo) exposes the Anthropic Messages protocol at
``{base_url}/v1/messages``. We keep one persistent ``httpx.AsyncClient`` for the
lifetime of the app (opened lazily, closed on shutdown) for the same reason as
the Ollama client — to amortise TLS + keep-alive setup across requests.

The rest of the app speaks an OpenAI-ish ``messages`` shape (``[{role, content}]``
with an optional leading ``system`` role). This client adapts that to the
Anthropic schema on the way out:
  - the ``system`` role is hoisted to the top-level ``system`` field;
  - optional ``images`` (base64) are attached to the *last* user message as
    ``image`` content blocks so the multimodal model can see them.

Streaming uses Anthropic SSE: we read ``data:`` lines and emit normalised deltas
matching the Ollama client's contract so callers don't care which provider runs.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
import json
import httpx

from app.core.config import settings


class MiMoClient:
    """Thin async wrapper around MiMo's Anthropic Messages API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or settings.mimo_base_url).rstrip("/")
        self.api_key = api_key or settings.mimo_api_key
        self._client: httpx.AsyncClient | None = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # trust_env=True: MiMo is a public endpoint, honour any corporate proxy.
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15, read=None, write=30, pool=15),
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    @staticmethod
    def _split_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Hoist leading/any system messages out; return (system, chat_messages)."""
        system_parts: list[str] = []
        chat: list[dict] = []
        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "system":
                if content:
                    system_parts.append(content if isinstance(content, str) else str(content))
                continue
            chat.append({"role": role, "content": content})
        system = "\n\n".join(p for p in system_parts if p) or None
        return system, chat

    @staticmethod
    def _attach_images(chat: list[dict], images: list[dict]) -> None:
        """Attach base64 image blocks to the last user message (in place).

        Each image dict: ``{"media_type": "image/jpeg", "data": "<base64>"}``.
        Converts that user message's content from a plain string into an
        Anthropic content-block array: image blocks first, then the text.
        """
        if not images:
            return
        # Find the last user message; fall back to appending one.
        idx = next((i for i in range(len(chat) - 1, -1, -1) if chat[i].get("role") == "user"), None)
        if idx is None:
            chat.append({"role": "user", "content": ""})
            idx = len(chat) - 1
        text = chat[idx].get("content")
        text = text if isinstance(text, str) else ""
        blocks: list[dict] = []
        for img in images:
            data = img.get("data")
            if not data:
                continue
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type") or "image/jpeg",
                        "data": data,
                    },
                }
            )
        if not blocks:
            return
        if text:
            blocks.append({"type": "text", "text": text})
        chat[idx]["content"] = blocks

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int | None = None,
        images: list[dict] | None = None,
        think: bool | None = None,  # False=关闭思考(实测首字快 4 倍), True=开启, None=服务端默认
    ) -> AsyncIterator[dict]:
        """Stream a MiMo completion.

        Yields the same shapes as the Ollama client:
          - {'thinking': str}  — incremental reasoning (if the model emits it)
          - {'content': str}   — incremental visible text
          - {'done': True}
        """
        if not self.api_key:
            raise RuntimeError(
                "MIMO_API_KEY 未配置：请在环境变量或 .env 中设置 MiMo Api Key。"
            )

        system, chat = self._split_messages(messages)
        if images:
            self._attach_images(chat, images)

        payload: dict = {
            "model": model or settings.mimo_model,
            "max_tokens": int(max_tokens or settings.mimo_max_tokens),
            "messages": chat,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
        }
        # 思考开关：MiMo 默认会先跑一段推理（实测要 17 秒才开始出正文），
        # think=False 时显式关闭，think=True 时显式打开，None 则沿用服务端默认。
        if think is True:
            payload["thinking"] = {"type": "enabled"}
        elif think is False:
            payload["thinking"] = {"type": "disabled"}
        if system:
            payload["system"] = system

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        client = self._ensure()
        url = f"{self.base_url}/v1/messages"
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"MiMo API {resp.status_code}: {body[:500]}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                etype = evt.get("type")
                if etype == "content_block_delta":
                    delta = evt.get("delta") or {}
                    dtype = delta.get("type")
                    if dtype == "thinking_delta":
                        t = delta.get("thinking")
                        if t:
                            yield {"thinking": t}
                    elif dtype == "text_delta":
                        c = delta.get("text")
                        if c:
                            yield {"content": c}
                elif etype == "message_stop":
                    yield {"done": True}
                    break
                elif etype == "error":
                    err = evt.get("error") or {}
                    raise RuntimeError(f"MiMo stream error: {err.get('message') or err}")


mimo = MiMoClient()
