from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_token
from app.models.kb import KBMember, KBPermission, KnowledgeBase
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user_id = int(payload["sub"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or disabled")
    return user


def is_admin(user: User) -> bool:
    """管理员判定：role == 'admin' 或用户名在 settings.admin_usernames。"""
    return user.role == "admin" or user.username in settings.admin_username_set


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


async def _load_kb_and_member(
    db: AsyncSession, user: User, kb_id: int
) -> tuple[KnowledgeBase, KBMember | None]:
    kb = (
        await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    ).scalar_one_or_none()
    if kb is None:
        raise HTTPException(404, "知识库不存在")
    if kb.owner_id == user.id:
        return kb, None
    member = (
        await db.execute(
            select(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    return kb, member


async def require_kb_read(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeBase:
    kb, member = await _load_kb_and_member(db, user, kb_id)
    # 公开 KB（管理员标记 is_public）任何登录用户可读，供公开官网 AI 使用。
    if kb.owner_id != user.id and member is None and not getattr(kb, "is_public", False):
        raise HTTPException(403, "无权访问")
    return kb


async def require_kb_write(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeBase:
    kb, member = await _load_kb_and_member(db, user, kb_id)
    if kb.owner_id == user.id:
        return kb
    if member is None or member.permission == KBPermission.read:
        raise HTTPException(403, "无上传权限")
    return kb
