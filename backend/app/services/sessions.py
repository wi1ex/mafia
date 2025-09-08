from __future__ import annotations
import uuid
import redis.asyncio as redis
from fastapi import Response
from ..settings import settings
from ..core.clients import get_redis
from ..core.security import create_access_token, create_refresh_token, decode_token

REFRESH_COOKIE = "rt"
COOKIE_PATH = "/api"

def _refresh_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

async def _set_refresh_cookie(resp: Response, token: str):
    resp.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=_refresh_ttl(),
        secure=True,
        httponly=True,
        samesite="strict",
        path=COOKIE_PATH,
        domain=settings.DOMAIN,
    )

async def _clear_refresh_cookie(resp: Response):
    resp.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH, domain=settings.DOMAIN)

async def _revoke_old_session(r: redis.Redis, user_id: int):
    prev = await r.get(f"user:{user_id}:session")
    if not prev:
        return
    prev_sid = prev.decode() if isinstance(prev, (bytes, bytearray)) else str(prev)

    pipe = r.pipeline()
    # стираем маркеры текущей сессии пользователя
    pipe.delete(f"user:{user_id}:session")
    # удаляем все выданные refresh для этой сессии
    async for key in r.scan_iter(match=f"sess:{prev_sid}:rt:*"):
        pipe.delete(key)
    # кикнем все сокеты этого пользователя
    pipe.publish("sio:kick", str(user_id))
    await pipe.execute()

async def new_login_session(resp: Response, *, user_id: int, role: str) -> str:
    r = get_redis()
    await _revoke_old_session(r, user_id)

    sid = uuid.uuid4().hex
    await r.setex(f"user:{user_id}:session", _refresh_ttl(), sid)

    rt, jti = create_refresh_token(sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await r.setex(f"sess:{sid}:rt:{jti}", _refresh_ttl(), 1)
    await _set_refresh_cookie(resp, rt)
    return sid

def issue_access_token(*, user_id: int, role: str, sid: str) -> str:
    return create_access_token(sub=user_id, role=role, sid=sid, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> bool:
    try:
        payload = decode_token(raw_refresh_jwt)
    except Exception:
        return False
    if payload.get("typ") != "refresh":
        return False

    user_id = int(payload.get("sub") or 0)
    sid = payload.get("sid")
    jti = payload.get("jti")
    if not user_id or not sid or not jti:
        return False

    r = get_redis()
    stored = await r.get(f"user:{user_id}:session")
    stored_sid = stored.decode() if isinstance(stored, (bytes, bytearray)) else stored
    if not stored_sid or stored_sid != sid:
        return False

    if not await r.exists(f"sess:{sid}:rt:{jti}"):
        return False

    # rotate only the refresh token + extend session TTLs
    await r.delete(f"sess:{sid}:rt:{jti}")
    new_rt, new_jti = create_refresh_token(sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await r.setex(f"sess:{sid}:rt:{new_jti}", _refresh_ttl(), 1)
    await _set_refresh_cookie(resp, new_rt)
    await r.expire(f"user:{user_id}:session", _refresh_ttl())
    return True

async def logout(resp: Response, *, user_id: int):
    r = get_redis()
    stored = await r.get(f"user:{user_id}:session")
    if stored:
        sid = stored.decode() if isinstance(stored, (bytes, bytearray)) else str(stored)
        pipe = r.pipeline()
        pipe.delete(f"user:{user_id}:session")
        async for key in r.scan_iter(match=f"sess:{sid}:rt:*"):
            pipe.delete(key)
        pipe.publish("sio:kick", str(user_id))
        await pipe.execute()
    await _clear_refresh_cookie(resp)
