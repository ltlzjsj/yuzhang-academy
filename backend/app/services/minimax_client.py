"""Async client for MiniMax's Anthropic-compatible Messages API.

MiniMax exposes the Anthropic Messages protocol at
``{base_url}/v1/messages``. The rest of the app uses a provider-neutral
streaming shape, so this client adapts MiniMax SSE responses into the same
``{"thinking": ...}``, ``{"content": ...}``, and ``{"done": True}``
deltas returned by the other LLM clients.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
import json

import httpx

from app.core.config import settings


class MiniMaxClient:
    """Thin async wrapper around MiniMax's Anthropic Messages API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or settings.minimax_base_url).rstrip("/")
        self.api_key = api_key or settings.minimax_api_key
        self._client: httpx.AsyncClient | None = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
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
        """Hoist system messages into Anthropic's top-level system field."""
        system_parts: list[str] = []
        chat: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content") or ""
            if role == "system":
                if content:
                    system_parts.append(content if isinstance(content, str) else str(content))
                continue
            if role in {"user", "assistant"}:
                chat.append({"role": role, "content": content})
        system = "\n\n".join(part for part in system_parts if part) or None
        return system, chat

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int | None = None,
        images: list[dict] | None = None,
        think: bool | None = None,
    ) -> AsyncIterator[dict]:
        """Stream a MiniMax completion via the Anthropic-compatible endpoint.

        MiniMax-M2.7 supports text content blocks through this endpoint. The
        app may pass RAG images for other providers; they are intentionally
        ignored here so M2.7 receives a valid text-only request.
        """
        del images, think

        if not self.api_key:
            raise RuntimeError(
                "MINIMAX_API_KEY is not configured. Set it in the environment or backend/.env."
            )

        system, chat = self._split_messages(messages)
        payload: dict = {
            "model": model or settings.minimax_model,
            "max_tokens": int(max_tokens or settings.minimax_max_tokens),
            "messages": chat,
            "stream": True,
            "temperature": temperature,
            "top_p": top_p,
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        client = self._ensure()
        url = f"{self.base_url}/v1/messages"
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"MiniMax API {resp.status_code}: {body[:500]}")
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

                event_type = evt.get("type")
                if event_type == "content_block_delta":
                    delta = evt.get("delta") or {}
                    delta_type = delta.get("type")
                    if delta_type == "thinking_delta":
                        thinking = delta.get("thinking")
                        if thinking:
                            yield {"thinking": thinking}
                    elif delta_type == "text_delta":
                        text = delta.get("text")
                        if text:
                            yield {"content": text}
                elif event_type == "message_stop":
                    yield {"done": True}
                    break
                elif event_type == "error":
                    err = evt.get("error") or {}
                    raise RuntimeError(f"MiniMax stream error: {err.get('message') or err}")


minimax = MiniMaxClient()
