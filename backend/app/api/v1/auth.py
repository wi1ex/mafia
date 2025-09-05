from __future__ import annotations
import json, secrets
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import redis.asyncio as redis
from ...db import get_session
from ...models.user import User
from ...schemas.auth import TelegramAuthIn, AuthOut, AuthPending, CompleteProfileIn, UserOut
from ...core.security import verify_telegram_auth, create_access_token
from ...core.redis import build_redis
from ...services.logs import log_action
from fastapi.responses import JSONResponse
from __future__ import annotations
import json, secrets
from fastapi import APIRouter, HTTPException, Depends, status, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import redis.asyncio as redis
from ...db import get_session
from ...models.user import User
from ...schemas.auth import TelegramAuthIn, AuthOut, AuthPending, CompleteProfileIn, UserOut
from ...core.security import verify_telegram_auth
from ...core.redis import build_redis
from ...services.logs import log_action
from ...services.sessions import new_login_session, issue_access_token, rotate_refresh, logout as logout_sess, REFRESH_COOKIE
from ..deps import get_current_user

router = APIRouter()
SESSION_TTL = 300

@router.post(
    "/telegram",
    response_model=AuthOut | AuthPending,                     # ← union
    responses={202: {"model": AuthPending}},                  # ← описываем 202
)
async def telegram_auth(payload: TelegramAuthIn, db: AsyncSession = Depends(get_session), resp: Response = None):
    data = payload.model_dump()
    if not verify_telegram_auth(data):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid telegram signature")

    res = await db.execute(select(User).where(User.id == payload.id))
    user = res.scalar_one_or_none()

    if user:
        await db.execute(update(User).where(User.id == user.id).values(last_login_at=func.now()))
        await db.commit()
        sid = await new_login_session(resp, user_id=user.id, role=user.role)
        access = await issue_access_token(user_id=user.id, role=user.role, sid=sid)
        return AuthOut(access_token=access, user=UserOut(id=user.id, username=user.username, nickname=user.nickname, name=user.name, photo_url=user.photo_url, role=user.role))

    sess = secrets.token_urlsafe(24)
    r: redis.Redis = build_redis()
    await r.setex(f"tg_auth:{sess}", SESSION_TTL, json.dumps({
        "id": payload.id,
        "username": payload.username,
        "photo_url": str(payload.photo_url) if payload.photo_url else None,
        "suggested_name": " ".join([x for x in [payload.first_name, payload.last_name] if x]).strip() or payload.username or f"id{payload.id}",
    }))
    return AuthPending(session=sess, suggested_username=payload.username or None, suggested_name=data.get("first_name"))

@router.post("/complete", response_model=AuthOut)
async def complete_profile(body: CompleteProfileIn, db: AsyncSession = Depends(get_session), resp: Response = None):
    r: redis.Redis = build_redis()
    raw = await r.get(f"tg_auth:{body.session}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session expired")
    await r.delete(f"tg_auth:{body.session}")
    info = json.loads(raw)

    exists = await db.execute(select(User.id).where(User.nickname == body.nickname))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="nickname_taken")

    user = User(
        id=int(info["id"]),
        username=info.get("username"),
        nickname=body.nickname,
        name=body.name,
        role="user",
        photo_url=info.get("photo_url"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await log_action(db, user_id=user.id, user_nickname=user.nickname, action="user_registered", details={"user_id": user.id})
    await db.commit()

    sid = await new_login_session(resp, user_id=user.id, role=user.role)
    access = await issue_access_token(user_id=user.id, role=user.role, sid=sid)
    return AuthOut(access_token=access, user=UserOut(id=user.id, username=user.username, nickname=user.nickname, name=user.name, photo_url=user.photo_url, role=user.role))

@router.get("/check-nickname")
async def check_nickname(nick: str = Query(..., pattern=r"^[a-zA-Z0-9_]{3,32}$"), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(User.id).where(User.nickname == nick))
    return {"available": res.scalar_one_or_none() is None}

@router.post("/refresh", response_model=AuthOut)
async def refresh(request: Request, resp: Response):
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no refresh")
    rotated = await rotate_refresh(resp, raw_refresh_jwt=raw)
    if not rotated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh")
    user_id, access = rotated
    # профиль фронту не обязателен при рефреше; можно опустить или вернуть кешированный минимум
    return AuthOut(access_token=access, user=UserOut(id=user_id, username=None, nickname=None, name=None, photo_url=None, role="user"))

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user), resp: Response = None):
    await logout_sess(resp, user_id=current_user.id)
    return {"status": "ok"}