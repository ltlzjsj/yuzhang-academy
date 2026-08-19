from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, is_admin
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)) -> UserOut:
    data = UserOut.model_validate(current)
    data.is_admin = is_admin(current)
    return data
