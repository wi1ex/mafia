from __future__ import annotations
from fastapi import APIRouter, Depends
from ...models.user import User
from ..deps import get_current_user
from ...schemas.auth import UserOut

router = APIRouter()

@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        photo_url=current_user.photo_url,
        role=current_user.role,
    )
