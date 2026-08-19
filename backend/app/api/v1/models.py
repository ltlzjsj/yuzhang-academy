from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.ollama_client import ollama

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(_: User = Depends(get_current_user)) -> dict:
    provider = settings.llm_provider.lower()
    if provider == "minimax":
        return {
            "items": [
                {
                    "name": settings.minimax_model,
                    "size": None,
                    "modified_at": None,
                    "family": "minimax",
                    "parameter_size": None,
                }
            ],
            "default_chat": settings.default_chat_model,
            "embed": settings.embed_model,
        }

    # MiMo (cloud) build: no local model registry to query. Return the single
    # configured multimodal model so the UI selector has a valid default.
    if provider != "ollama":
        return {
            "items": [
                {
                    "name": settings.mimo_model,
                    "size": None,
                    "modified_at": None,
                    "family": "mimo",
                    "parameter_size": None,
                }
            ],
            "default_chat": settings.default_chat_model,
            "embed": settings.embed_model,
        }
    try:
        raw = await ollama.list_models()
    except Exception as e:
        raise HTTPException(502, f"连接 Ollama 失败: {e}")
    items = [
        {
            "name": m.get("name"),
            "size": m.get("size"),
            "modified_at": m.get("modified_at"),
            "family": (m.get("details") or {}).get("family"),
            "parameter_size": (m.get("details") or {}).get("parameter_size"),
        }
        for m in raw
    ]
    return {
        "items": items,
        "default_chat": settings.default_chat_model,
        "embed": settings.embed_model,
    }
