from datetime import datetime
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = None
    model: str | None = None
    system_prompt: str = ""
    rag_enabled: bool = False
    kb_ids: list[int] | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    top_p: float = Field(default=0.9, ge=0, le=1)
    top_k: int = Field(default=6, ge=1, le=20)
    rerank: bool = False


class ConversationUpdate(BaseModel):
    title: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    rag_enabled: bool | None = None
    kb_ids: list[int] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    rerank: bool | None = None


class ConversationOut(BaseModel):
    id: int
    title: str
    model: str
    system_prompt: str
    rag_enabled: bool
    kb_ids: list[int] | None
    temperature: float
    top_p: float
    top_k: int
    rerank: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: list | None
    images: list | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSendIn(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=20000)
    model: str | None = None
    system_prompt: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    rag_enabled: bool | None = None
    kb_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    rerank: bool | None = None
    # When False, disables the model's hidden reasoning trace (qwen3 etc.).
    # Persisted per-conversation via `conversations.params["think"]`.
    think: bool | None = None
