from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.route_utils import log_route
from ...db import get_session
from ...models.user import User
from ...schemas import UserOut
from ...services.sessions import get_identity, Identity
from ...services.storage_minio import presign_avatar

router = APIRouter()


@log_route("users.profile_info")
@router.get("/profile_info", response_model=UserOut)
async def profile_info(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    user = await db.get(User, ident["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return UserOut(
        id=user.id,
        username=user.username,
        photo_url=presign_avatar(user.photo_url),
        role=user.role,
    )
