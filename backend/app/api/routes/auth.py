from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ...db import get_session
from ...models.user import User
from ...core.security import verify_telegram_auth, decode_token
from ...services.sessions import (
    new_login_session,
    issue_access_token,
    rotate_refresh,
    logout as sess_logout,
    REFRESH_COOKIE,
    COOKIE_PATH,
)
from ...services.storage_minio import download_telegram_photo, put_avatar
from ...core.logging import log_action
from ...schemas import TelegramAuthIn, AccessTokenOut, Ok
from ...settings import settings
from ...core.route_utils import log_route

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
        if payload.username:
            username = payload.username
            taken = (await db.execute(select(1).where(User.username == username).limit(1))).first() is not None
            if taken:
                username = f'user{uid}'
        else:
            username = f'user{uid}'
        filename = None
        if payload.photo_url and (not user or not user.photo_url):
            photo = await download_telegram_photo(payload.photo_url)
            if photo:
                content, ct = photo
                filename = put_avatar(uid, content, ct)
        user = User(id=uid, username=username, role="user", photo_url=filename)
        db.add(user)
        await db.commit()

    await log_action(db, user_id=user.id, username=user.username, action="register" if new_user else "login",
                     details={"user_id": user.id, "username": user.username, "role": user.role})

    at = await new_login_session(resp, user_id=user.id, role=user.role)
    return AccessTokenOut(access_token=at)


@log_route("auth.refresh")
@router.post("/refresh", response_model=AccessTokenOut)
async def refresh(resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh cookie")

    ok, uid, _sid = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    at = issue_access_token(user_id=uid, role=user.role)
    return AccessTokenOut(access_token=at)


@log_route("auth.logout")
@router.post("/logout", response_model=Ok)
async def logout(resp: Response, request: Request) -> Ok:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            p = decode_token(raw)
            if p.get("typ") == "refresh":
                uid = int(p.get("sub") or 0)
                sid = str(p.get("sid") or "")
                await sess_logout(resp, user_id=uid, sid=sid or None)
                return Ok()
        except Exception:
            pass
    resp.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, domain=settings.DOMAIN, samesite="strict")
    return Ok()
