from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    role: str
    content: str = Field(default="", max_length=20000)


class AgentChatIn(BaseModel):
    """Stateless agent dialogue (历史名人 / 首页导览).

    Unlike `/chat/stream`, nothing is persisted: the running dialogue is sent by
    the client each turn, so these persona chats never appear in the user's main
    conversation history.
    """

    messages: list[AgentMessage] = Field(default_factory=list)
    system_prompt: str = ""
    kb_ids: list[int] = Field(default_factory=list)
    rag_enabled: bool = True
    temperature: float | None = None
    top_p: float | None = None
