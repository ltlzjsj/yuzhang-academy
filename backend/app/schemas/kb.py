from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class KBCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    chunk_size: int = Field(default=512, ge=128, le=2048)
    chunk_overlap: int = Field(default=50, ge=0, le=500)
    qa_enabled: bool = False
    qa_model: str | None = None
    qa_pairs_per_chunk: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def check_chunk_overlap(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KBUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    chunk_size: int | None = Field(default=None, ge=128, le=2048)
    chunk_overlap: int | None = Field(default=None, ge=0, le=500)
    qa_enabled: bool | None = None
    qa_model: str | None = None
    qa_pairs_per_chunk: int | None = Field(default=None, ge=1, le=3)
    is_public: bool | None = None

    @model_validator(mode="after")
    def check_chunk_overlap(self):
        if (
            self.chunk_size is not None
            and self.chunk_overlap is not None
            and self.chunk_overlap >= self.chunk_size
        ):
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


class KBOut(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    qa_enabled: bool
    qa_model: str | None
    qa_pairs_per_chunk: int = 2
    qdrant_collection: str
    is_public: bool = False
    created_at: datetime
    # Computed
    document_count: int = 0
    chunk_count: int = 0

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: int
    kb_id: int
    filename: str
    size_bytes: int
    pages: int
    status: str
    progress: int
    error: str | None
    metadata: dict | None = Field(default=None, validation_alias="meta")
    image_count: int = 0
    image_preview: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentMetadataUpdate(BaseModel):
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ChunkOut(BaseModel):
    id: int
    document_id: int
    kb_id: int
    seq: int
    text: str
    page: int | None
    token_count: int
    bbox: list | dict | None = None
    metadata: dict | None = None

    class Config:
        from_attributes = True
