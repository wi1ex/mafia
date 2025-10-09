from __future__ import annotations
import re
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from ...db import get_session
from ...models.user import User
from ...schemas import UserOut, Identity, UsernameUpdateIn, AvatarUploadOut, Ok
from ...core.security import get_identity
from ...core.decorators import log_route, rate_limited
from ...services.storage_minio import put_avatar, delete_avatars, ALLOWED_CT, MAX_BYTES
from ...core.logging import log_action

router = APIRouter()


@log_route("users.profile_info")
@rate_limited(lambda ident, **_: f"rl:profile_info:{ident['id']}", limit=5, window_s=1)
@router.get("/profile_info", response_model=UserOut)
async def profile_info(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    user = await db.get(User, int(ident["id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return UserOut(
        id=user.id,
        username=user.username,
        avatar_name=user.avatar_name,
        role=user.role,
    )


@log_route("users.update_username")
@rate_limited(lambda ident, **_: f"rl:update_username:{ident['id']}", limit=1, window_s=1)
@router.patch("/username", response_model=UserOut)
async def update_username(payload: UsernameUpdateIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    uid = int(ident["id"])
    new = (payload.username or "").strip()

    USERNAME_RE = re.compile(r"^[a-zA-Zа-яА-Я0-9._-]{2,32}$")
    if not USERNAME_RE.match(new):
        raise HTTPException(status_code=422, detail="invalid_username_format")

    if new.lower().startswith("user"):
        raise HTTPException(status_code=422, detail="reserved_prefix")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if user.username == new:
        return UserOut(id=user.id, username=user.username, avatar_name=user.avatar_name, role=user.role)

    exists = await db.scalar(select(1).where(User.username == new, User.id != uid).limit(1))
    if exists:
        raise HTTPException(status_code=409, detail="username_taken")

    await db.execute(update(User).where(User.id == uid).values(username=new))
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=new,
        action="username_changed",
        details=f"Изменение никнейма: {user.username} -> {new}",
    )

    user.username = new
    return UserOut(id=user.id, username=user.username, avatar_name=user.avatar_name, role=user.role)


@log_route("users.upload_avatar")
@rate_limited(lambda ident, **_: f"rl:upload_avatar:{ident['id']}", limit=1, window_s=1)
@router.post("/avatar", response_model=AvatarUploadOut)
async def upload_avatar(file: UploadFile = File(...), ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> AvatarUploadOut:
    uid = int(ident["id"])
    ct = (file.content_type or "").split(";")[0].strip().lower()

    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=415, detail="unsupported_media_type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty_file")

    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    name = put_avatar(uid, data, ct)
    if not name:
        raise HTTPException(status_code=422, detail="bad_image")

    await db.execute(update(User).where(User.id == uid).values(avatar_name=name))
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_updated",
        details="Изменение аватара",
    )

    return AvatarUploadOut(avatar_name=name)


@log_route("users.delete_avatar")
@rate_limited(lambda ident, **_: f"rl:delete_avatar:{ident['id']}", limit=1, window_s=1)
@router.delete("/avatar", response_model=Ok)
async def delete_avatar(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    await db.execute(update(User).where(User.id == uid).values(avatar_name=None))
    await db.commit()
    try:
        delete_avatars(uid)
    except Exception:
        pass

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_deleted",
        details="Удаление аватара",
    )

    return Ok()
