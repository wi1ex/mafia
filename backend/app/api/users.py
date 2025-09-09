from __future__ import annotations
from fastapi import APIRouter, Depends
from ..models.user import User
from ..services.storage_minio import presign_avatar
from ..services.sessions import get_current_user


router = APIRouter()


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "photo_url": presign_avatar(current_user.photo_url) if current_user.photo_url else None,
        "role": current_user.role
    }
