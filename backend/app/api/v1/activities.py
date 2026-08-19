"""书院活动资讯：公开读取 + 管理后台增删改。

公开官网（活动资讯页 / 首页动态）读取已发布活动，无需登录；
新增 / 编辑 / 删除仅限管理员（与知识库、题库一致的 require_admin 策略）。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_admin
from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import (
    ActivityCreate,
    ActivityOut,
    ActivityUpdate,
    build_image_url,
)

router = APIRouter(prefix="/activities", tags=["activities"])

_VALID_STATUS = {"open", "ongoing", "closed"}


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    return value if value in _VALID_STATUS else "open"


def _to_out(a: Activity) -> ActivityOut:
    data = ActivityOut.model_validate(a)
    data.image_url = build_image_url(a.image)
    if not data.highlights:
        data.highlights = []
    return data


@router.get("", response_model=list[ActivityOut])
async def list_activities(
    category: str | None = None,
    include_unpublished: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """活动列表。默认仅返回已发布活动（公开）。

    `include_unpublished=true` 仅供管理后台预览（此处不强制鉴权，
    因为未发布内容并非敏感数据；如需严格隐藏可改用 require_admin）。
    """
    stmt = select(Activity)
    if not include_unpublished:
        stmt = stmt.where(Activity.is_published.is_(True))
    if category and category != "全部":
        stmt = stmt.where(Activity.category == category)
    stmt = stmt.order_by(Activity.sort_order.desc(), Activity.created_at.desc()).limit(
        min(max(limit, 1), 200)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_out(a) for a in rows]


@router.get("/{activity_id}", response_model=ActivityOut)
async def get_activity(activity_id: int, db: AsyncSession = Depends(get_db)):
    a = await db.get(Activity, activity_id)
    if a is None or not a.is_published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动不存在")
    return _to_out(a)


@router.post("", response_model=ActivityOut, status_code=201)
async def create_activity(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    payload = data.model_dump()
    payload["status"] = _normalize_status(payload.get("status")) or "open"
    a = Activity(**payload)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return _to_out(a)


@router.patch("/{activity_id}", response_model=ActivityOut)
async def update_activity(
    activity_id: int,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    a = await db.get(Activity, activity_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动不存在")
    fields = data.model_dump(exclude_unset=True)
    if "status" in fields:
        fields["status"] = _normalize_status(fields["status"]) or a.status
    for field, value in fields.items():
        setattr(a, field, value)
    await db.commit()
    await db.refresh(a)
    return _to_out(a)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    a = await db.get(Activity, activity_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "活动不存在")
    await db.delete(a)
    await db.commit()
