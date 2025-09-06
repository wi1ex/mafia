from __future__ import annotations
from fastapi import APIRouter, Depends
from ...models.user import User
from ..deps import get_current_user
from ...schemas.auth import UserOut
from ...services.storage_minio import presign_avatar

router = APIRouter()

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    avatar = presign_avatar(current_user.photo_url) if current_user.photo_url else None
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        photo_url=avatar,
        role=current_user.role,
    )
