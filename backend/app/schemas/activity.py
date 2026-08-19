from datetime import datetime
from urllib.parse import quote

from pydantic import BaseModel, Field

_VALID_STATUS = {"open", "ongoing", "closed"}


def build_image_url(image: str | None) -> str | None:
    """把存储的 image 字段转成可直接使用的 URL。

    - 空 → None
    - 以 http(s):// 或 / 开头 → 原样返回
    - 其它视为 academy 资源相对路径 → /api/v1/assets/academy/<编码路径>
    """
    src = (image or "").strip()
    if not src:
        return None
    if src.startswith(("http://", "https://", "/")):
        return src
    return "/api/v1/assets/academy/" + "/".join(quote(seg) for seg in src.split("/"))


class ActivityBase(BaseModel):
    category: str = Field(default="书院公告", max_length=32)
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(default="", max_length=512)
    body: str = ""
    event_date: str = Field(default="", max_length=64)
    period: str = Field(default="", max_length=128)
    place: str = Field(default="", max_length=256)
    audience: str = Field(default="", max_length=128)
    status: str = "open"
    highlights: list[str] = Field(default_factory=list)
    image: str = Field(default="", max_length=512)
    is_published: bool = True
    sort_order: int = 0


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    category: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, min_length=1, max_length=256)
    summary: str | None = Field(default=None, max_length=512)
    body: str | None = None
    event_date: str | None = Field(default=None, max_length=64)
    period: str | None = Field(default=None, max_length=128)
    place: str | None = Field(default=None, max_length=256)
    audience: str | None = Field(default=None, max_length=128)
    status: str | None = None
    highlights: list[str] | None = None
    image: str | None = Field(default=None, max_length=512)
    is_published: bool | None = None
    sort_order: int | None = None


class ActivityOut(ActivityBase):
    id: int
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
