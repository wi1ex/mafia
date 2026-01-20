from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ...models.user import User
from ...models.update import SiteUpdate, UpdateRead
from ...core.db import get_session
from ...core.settings import settings
from ...security.parameters import get_cached_settings
from ...core.logging import log_action
from ...security.decorators import log_route
from ...security.auth_tokens import verify_telegram_auth, create_access_token, parse_refresh_token
from ...security.sessions import new_login_session, rotate_refresh, logout as sess_logout
from ...schemas.common import Ok
from ...schemas.auth import TelegramAuthIn, AccessTokenOut
from ...services.minio import download_telegram_photo, put_avatar
from ..utils import touch_user_last_login

router = APIRouter()


@log_route("auth.telegram")
@router.post("/telegram", response_model=AccessTokenOut)
async def telegram(payload: TelegramAuthIn, resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    if not get_cached_settings().registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="registration_disabled")

    data_for_sig = payload.model_dump(exclude_none=True)
    if not verify_telegram_auth(data_for_sig):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid telegram auth")

    new_user = False
    uid = int(payload.id)
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user and user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")
    if not user:
        new_user = True
        base_username = (payload.username or "")[:20]
        if base_username:
            exists = await db.scalar(select(1).where(User.username == base_username).limit(1))
            username = base_username if not exists else f"user{uid}"
        else:
            username = f"user{uid}"

        filename = None
        if payload.photo_url:
            photo = await download_telegram_photo(payload.photo_url)
            if photo:
                content, ct = photo
                filename = put_avatar(uid, content, ct)

        user = User(id=uid, username=username, role="user", avatar_name=filename)
        db.add(user)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
            if user:
                new_user = False
            else:
                raise

        if new_user:
            try:
                rows = await db.execute(select(SiteUpdate.id))
                ids = [int(r[0]) for r in rows.all() if r and r[0] is not None]
                if ids:
                    now = datetime.now(timezone.utc)
                    for upd_id in ids:
                        db.add(UpdateRead(user_id=uid, update_id=upd_id, read_at=now))
                    await db.commit()
            except Exception:
                await db.rollback()

    raw_pwa = (request.headers.get("x-pwa") or "").strip().lower()
    is_pwa = raw_pwa in {"1", "true", "yes", "pwa"}
    action = "register" if new_user else ("login_pwa" if is_pwa else "login")

    await log_action(
        db,
        user_id=user.id,
        username=user.username,
        action=action,
        details=f"Вход пользователя: user_id={user.id} username={user.username}",
    )

    access_token, sid = await new_login_session(resp, user_id=user.id, username=user.username, role=user.role)
    await touch_user_last_login(db, user.id)
    return AccessTokenOut(access_token=access_token, sid=sid, is_new=new_user)


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
    if user.deleted_at:
        await sess_logout(resp, user_id=uid, sid=sid or None)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    access_token = create_access_token(sub=uid, username=user.username, role=user.role, sid=sid or "", ttl_minutes=settings.ACCESS_EXP_MIN)
    return AccessTokenOut(access_token=access_token, sid=sid or "")


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
