from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select, exists, func, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ...models.user import User
from ...core.db import get_session
from ...core.settings import settings
from ...security.parameters import get_cached_settings
from ...core.logging import log_action
from ...security.decorators import log_route
from ...security.auth_tokens import create_access_token, parse_refresh_token
from ...security.passwords import hash_password, verify_password
from ...security.sessions import new_login_session, rotate_refresh, logout as sess_logout
from ...schemas.common import Ok
from ...schemas.auth import AccessTokenOut, PasswordLoginIn, PasswordRegisterIn
from ..utils import (
    touch_user_last_login,
    normalize_username,
    normalize_password,
    find_user_by_username,
    generate_user_id,
    init_updates_read,
)

router = APIRouter()


@log_route("auth.register")
@router.post("/register", response_model=AccessTokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: PasswordRegisterIn, resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    if not get_cached_settings().registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="registration_disabled")

    if payload.accept_rules is not True:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="rules_required")

    username = normalize_username(payload.username)
    password = normalize_password(payload.password)

    exists_case_ins = await db.scalar(select(exists().where(func.lower(User.username).eq(func.lower(literal(username))))))
    if exists_case_ins:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")

    user_id = await generate_user_id(db)
    user = User(
        id=user_id,
        username=username,
        role="user",
        password_hash=hash_password(password),
        password_temp=False,
        telegram_id=None,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")

    await init_updates_read(db, user_id)

    raw_pwa = (request.headers.get("x-pwa") or "").strip().lower()
    is_pwa = raw_pwa in {"1", "true", "yes", "pwa"}
    action = "register_pwa" if is_pwa else "register"

    await log_action(
        db,
        user_id=user_id,
        username=username,
        action=action,
        details=f"Регистрация пользователя: user_id={user_id} username={username}",
    )

    access_token, sid = await new_login_session(resp, user_id=user_id, username=username, role="user")
    await touch_user_last_login(db, user_id)
    return AccessTokenOut(access_token=access_token, sid=sid, is_new=True)


@log_route("auth.login")
@router.post("/login", response_model=AccessTokenOut)
async def login(payload: PasswordLoginIn, resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    username = normalize_username(payload.username)
    password = normalize_password(payload.password)

    user = await find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")
    if not user.password_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_not_set")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    raw_pwa = (request.headers.get("x-pwa") or "").strip().lower()
    is_pwa = raw_pwa in {"1", "true", "yes", "pwa"}
    action = "login_pwa" if is_pwa else "login"

    await log_action(
        db,
        user_id=int(user.id),
        username=user.username,
        action=action,
        details=f"Вход пользователя: user_id={int(user.id)} username={user.username}",
    )

    access_token, sid = await new_login_session(resp, user_id=int(user.id), username=user.username, role=user.role)
    await touch_user_last_login(db, int(user.id))
    return AccessTokenOut(access_token=access_token, sid=sid)


@log_route("auth.refresh")
@router.post("/refresh", response_model=AccessTokenOut)
async def refresh(resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    raw = request.cookies.get("rt")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh cookie")

    ok, user_id, sid = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    if user.deleted_at:
        await sess_logout(resp, user_id=user_id, sid=sid or None)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    access_token = create_access_token(sub=user_id, username=user.username, role=user.role, sid=sid or "", ttl_minutes=settings.ACCESS_EXP_MIN)
    return AccessTokenOut(access_token=access_token, sid=sid or "")


@log_route("auth.logout")
@router.post("/logout", response_model=Ok)
async def logout(resp: Response, request: Request) -> Ok:
    raw = request.cookies.get("rt")
    if raw:
        ok, user_id, sid, _ = parse_refresh_token(raw)
        if ok:
            await sess_logout(resp, user_id=user_id, sid=sid or None)
            return Ok()

    resp.delete_cookie("rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    return Ok()
