from __future__ import annotations
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ...db import get_session
from ...models.user import User
from ...core.security import verify_telegram_auth, create_access_token, parse_refresh_token
from ...services.sessions import new_login_session, rotate_refresh, logout as sess_logout
from ...services.storage_minio import download_telegram_photo, put_avatar
from ...core.logging import log_action
from ...schemas import TelegramAuthIn, AccessTokenOut, Ok
from ...settings import settings
from ...core.decorators import log_route

router = APIRouter()


@log_route("auth.telegram")
@router.post("/telegram", response_model=AccessTokenOut)
async def login_with_telegram(payload: TelegramAuthIn, resp: Response, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    data_for_sig = payload.model_dump(exclude_none=True)
    if not verify_telegram_auth(data_for_sig):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid telegram auth")

    new_user = False
    uid = int(payload.id)
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        new_user = True
        username = payload.username or f"user{uid}"
        if await db.scalar(select(1).where(User.username == username).limit(1)):
            username = f"user{uid}"

        filename = None
        if payload.photo_url:
            photo = await download_telegram_photo(payload.photo_url)
            if photo:
                content, ct = photo
                filename = put_avatar(uid, content, ct)

        user = User(id=uid, username=username, role="user", avatar_name=filename)
        db.add(user)
        await db.commit()

    await log_action(
        db,
        user_id=user.id,
        username=user.username,
        action="register" if new_user else "login",
        details=f"Вход пользователя: user_id={user.id} username={user.username}",
    )

    at, sid = await new_login_session(resp, user_id=user.id, username=user.username, role=user.role)

    await db.execute(update(User).where(User.id == user.id).values(last_login_at=func.now()))
    await db.commit()

    return AccessTokenOut(access_token=at, sid=sid)


@log_route("auth.refresh")
@router.post("/refresh", response_model=AccessTokenOut)
async def refresh(resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    raw = request.cookies.get("rt")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh cookie")

    ok, uid, sid = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    at = create_access_token(sub=uid, username=user.username, role=user.role, sid=sid or "", ttl_minutes=settings.ACCESS_EXP_MIN)

    await db.execute(update(User).where(User.id == user.id).values(last_login_at=func.now()))
    await db.commit()

    return AccessTokenOut(access_token=at, sid=sid or "")


@log_route("auth.logout")
@router.post("/logout", response_model=Ok)
async def logout(resp: Response, request: Request) -> Ok:
    raw = request.cookies.get("rt")
    if raw:
        ok, uid, sid, _ = parse_refresh_token(raw)
        if ok:
            await sess_logout(resp, user_id=uid, sid=sid or None)
            return Ok()

    resp.delete_cookie("rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    return Ok()
