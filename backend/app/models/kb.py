from datetime import datetime
from enum import Enum
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KBPermission(str, Enum):
    owner = "owner"
    write = "write"
    read = "read"


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(String(1024), default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    embedding_model: Mapped[str] = mapped_column(String(128), default="bge-m3:latest")
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    qa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    qa_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # How many Q/A pairs the generator should aim for per chunk (1..3).
    # Hard upper bound kept at 3 to keep generation cost bounded.
    qa_pairs_per_chunk: Mapped[int] = mapped_column(Integer, default=2)
    qdrant_collection: Mapped[str] = mapped_column(String(128), unique=True)
    # 公开知识库：任何登录用户可读（供公开官网的问书院/答题/名人对话使用）。
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KBMember(Base):
    __tablename__ = "kb_members"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kb_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    permission: Mapped[KBPermission] = mapped_column(SAEnum(KBPermission), default=KBPermission.read)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
