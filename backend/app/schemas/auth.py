from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: EmailStr | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool
    # 有效管理员（role == 'admin' 或用户名在 ADMIN_USERNAMES），前端据此显示管理后台。
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True
