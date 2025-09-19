from __future__ import annotations
from fastapi import APIRouter, Depends
from ...models.user import User
from ...schemas import UserOut
from ...services.storage_minio import presign_avatar
from ...services.sessions import get_current_user
from ...core.route_utils import log_route

router = APIRouter()

@log_route("users.profile_info")
@router.get("/profile_info", response_model=UserOut)
async def profile_info(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        photo_url=presign_avatar(current_user.photo_url) if current_user.photo_url else None,
        role=current_user.role,
    )
