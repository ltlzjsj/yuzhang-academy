"""Provider-agnostic chat entrypoint.

Dispatches streaming chat to the configured LLM provider (``settings.llm_provider``):
  - "mimo"   → Xiaomi MiMo cloud (Anthropic Messages API, multimodal)
  - "ollama" → local Ollama (legacy geological build)

Callers (api/v1/chat.py) depend only on this module so swapping providers is a
config change, not a code change. The ``images`` argument is honoured by the
MiMo provider and ignored by Ollama (text-only path).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.config import settings


async def chat_stream(
    model: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    top_p: float = 0.9,
    think: bool | None = None,
    images: list[dict] | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict]:
    provider = (settings.llm_provider or "mimo").lower()
    if provider == "ollama":
        from app.services.ollama_client import ollama

        async for delta in ollama.chat_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            think=think,
        ):
            yield delta
        return

    if provider == "minimax":
        from app.services.minimax_client import minimax

        async for delta in minimax.chat_stream(
            model=model or settings.minimax_model,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            images=images,
            think=think,
            max_tokens=max_tokens,
        ):
            yield delta
        return

    # Default: MiMo
    from app.services.mimo_client import mimo

    async for delta in mimo.chat_stream(
        model=model or settings.mimo_model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        images=images,
        think=think,
        max_tokens=max_tokens,
    ):
        yield delta


async def aclose() -> None:
    """Close whichever provider client is open (called from app lifespan)."""
    provider = (settings.llm_provider or "mimo").lower()
    try:
        if provider == "ollama":
            from app.services.ollama_client import ollama

            await ollama.aclose()
        elif provider == "minimax":
            from app.services.minimax_client import minimax

            await minimax.aclose()
        else:
            from app.services.mimo_client import mimo

            await mimo.aclose()
    except Exception:
        pass
