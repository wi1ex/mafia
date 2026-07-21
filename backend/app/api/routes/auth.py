from __future__ import annotations
from sqlalchemy import select, exists, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, HTTPException, Depends, Response, Request, status
from ...models.user import User
from ...core.db import get_session
from ...core.settings import settings
from ...security.parameters import get_cached_settings
from ...core.logging import log_action
from ...security.decorators import log_route
from ...security.auth_tokens import (
    AUTH_SESSION_SID_HEADER,
    create_access_token,
    parse_refresh_token,
    refresh_cookie_matches_scope,
)
from ...security.passwords import hash_password_async, password_needs_rehash, verify_password_async
from ...security.sessions import new_login_session, rotate_refresh, logout as sess_logout
from ...services.user_cache import refresh_user_profile_cache
from ...services.text_moderation import enforce_clean_text
from ...services.nickname_limits import FREE_NICKNAME_CHANGE_LIMIT
from ...schemas.common import Ok
from ...schemas.auth import AccessTokenOut, PasswordLoginIn, PasswordRegisterIn
from ..utils import (
    touch_user_last_login,
    normalize_username,
    normalize_password,
    find_user_by_username,
    generate_user_id,
)

router = APIRouter()


@router.post("/register", response_model=AccessTokenOut, status_code=status.HTTP_201_CREATED)
@log_route("auth.register")
async def register(payload: PasswordRegisterIn, resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    if not get_cached_settings().registration_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="registration_disabled")

    if payload.accept_rules is not True:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="rules_required")

    if payload.confirm_adult is not True:
        raise HTTPException(status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail="adult_confirmation_required")

    username = normalize_username(payload.username)
    password = normalize_password(payload.password)
    if username.lower().startswith(("deleted_", "user_")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_username_format")

    enforce_clean_text(field="username", label="Никнейм", value=username)

    exists_case_ins = await db.scalar(select(exists().where(func.lower(User.username) == username.lower())))
    if exists_case_ins:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")

    user_id = await generate_user_id(db)
    user = User(
        id=user_id,
        username=username,
        role="user",
        password_hash=await hash_password_async(password),
        password_temp=False,
        telegram_id=None,
        tg_invites_enabled=True,
        allow_friend_requests=True,
        nickname_changes_left=FREE_NICKNAME_CHANGE_LIMIT,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_taken")

    raw_pwa = (request.headers.get("x-pwa") or "").strip().lower()
    is_pwa = raw_pwa in {"1", "true", "yes", "pwa"}
    action = "register_pwa" if is_pwa else "register"

    await log_action(
        db,
        user_id=user_id,
        username=username,
        action=action,
        details=(
            f"Регистрация пользователя: user_id={user_id} username={username}; "
            "rules_accepted=true; adult_confirmed=true"
        ),
    )

    await refresh_user_profile_cache(db, user_id)
    access_token, sid = await new_login_session(resp, user_id=user_id, username=username, role="user")
    await touch_user_last_login(db, user_id)
    return AccessTokenOut(access_token=access_token, sid=sid, is_new=True)


@router.post("/login", response_model=AccessTokenOut)
@log_route("auth.login")
async def login(payload: PasswordLoginIn, resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    username = normalize_username(payload.username)
    password = normalize_password(payload.password, allow_whitespace=True)

    user = await find_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")
    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")
    if not user.password_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_not_set")
    if not await verify_password_async(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    if password_needs_rehash(user.password_hash):
        user.password_hash = await hash_password_async(password)
        await db.commit()

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

    await refresh_user_profile_cache(db, int(user.id))
    access_token, sid = await new_login_session(resp, user_id=int(user.id), username=user.username, role=user.role)
    await touch_user_last_login(db, int(user.id))
    return AccessTokenOut(access_token=access_token, sid=sid)


@router.post("/refresh", response_model=AccessTokenOut)
@log_route("auth.refresh")
async def refresh(resp: Response, request: Request, db: AsyncSession = Depends(get_session)) -> AccessTokenOut:
    raw = request.cookies.get("rt")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh cookie")

    token_ok, _, _, _ = parse_refresh_token(raw)
    expected_sid = request.headers.get(AUTH_SESSION_SID_HEADER, "")
    if token_ok and not refresh_cookie_matches_scope(raw, expected_sid):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_changed")

    ok, user_id, sid = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    if user.deleted_at:
        await sess_logout(resp, user_id=user_id, sid=sid or None)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    await refresh_user_profile_cache(db, int(user_id))
    access_token = create_access_token(sub=user_id, username=user.username, role=user.role, sid=sid or "", ttl_minutes=settings.ACCESS_EXP_MIN)
    return AccessTokenOut(access_token=access_token, sid=sid or "")


@router.post("/logout", response_model=Ok)
@log_route("auth.logout")
async def logout(resp: Response, request: Request) -> Ok:
    raw = request.cookies.get("rt")
    if raw:
        ok, user_id, sid, _ = parse_refresh_token(raw)
        if ok:
            expected_sid = request.headers.get(AUTH_SESSION_SID_HEADER, "")
            if not refresh_cookie_matches_scope(raw, expected_sid):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_changed")

            await sess_logout(resp, user_id=user_id, sid=sid or None)
            return Ok()

    resp.delete_cookie("rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    return Ok()
