from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ..db import get_session
from ..models.user import User
from ..core.security import verify_telegram_auth, decode_token
from ..services.sessions import (
    new_login_session,
    issue_access_token,
    rotate_refresh,
    logout as logout_sess,
    REFRESH_COOKIE,
)
from ..services.storage_minio import download_telegram_photo, put_avatar, presign_avatar
from ..core.logging import log_action
from ..schemas import TelegramAuthIn, TokenOut, UserOut, Ok
from ..settings import settings
from ..core.route_utils import log_route


router = APIRouter()


@log_route("auth.telegram")
@router.post("/telegram", response_model=TokenOut)
async def login_with_telegram(payload: TelegramAuthIn, resp: Response, db: AsyncSession = Depends(get_session)) -> TokenOut:
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
                     details={
                         "user_id": user.id,
                         "username": user.username,
                         "role": user.role,
                     })
    at = await new_login_session(resp, user_id=user.id, role=user.role)
    return TokenOut(access_token=at, user=UserOut(
        id=user.id,
        username=user.username,
        photo_url=presign_avatar(user.photo_url) if user.photo_url else None,
        role=user.role,
    ))


@log_route("auth.refresh")
@router.post("/refresh", response_model=TokenOut)
async def refresh(resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> TokenOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh cookie")
    try:
        p = decode_token(raw)
        if p.get("typ") != "refresh":
            raise ValueError
        uid = int(p.get("sub") or 0)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    ok = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    at = issue_access_token(user_id=uid, role=user.role)
    return TokenOut(access_token=at, user=UserOut(
        id=user.id,
        username=user.username,
        photo_url=presign_avatar(user.photo_url) if user.photo_url else None,
        role=user.role,
    ))


@log_route("auth.logout")
@router.post("/logout", response_model=Ok)
async def logout(resp: Response, request: Request) -> Ok:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            p = decode_token(raw)
            if p.get("typ") == "refresh":
                await logout_sess(resp, user_id=int(p.get("sub") or 0))
                return Ok()
        except Exception:
            pass
    resp.delete_cookie(REFRESH_COOKIE, path="/api", domain=settings.DOMAIN)
    return Ok()
