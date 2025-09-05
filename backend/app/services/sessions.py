from __future__ import annotations
import asyncio
import redis.asyncio as redis
from fastapi import Response
from ..settings import settings
from ..core.redis import build_redis
from ..core.security import create_access_token, create_refresh_token, decode_token

# Keys:
# user:{uid}:session -> sid
# sess:{sid}:status -> 1 (ttl = refresh ttl)
# sess:{sid}:rt:{jti} -> 1 (ttl = refresh ttl), единственный валидный jti в рамках sid

REFRESH_COOKIE = "rt"
COOKIE_PATH = "/api"  # фронт и API на одном домене через nginx

def _refresh_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400

async def _revoke_old_session(r: redis.Redis, user_id: int):
    prev = await r.get(f"user:{user_id}:session")
    if prev:
        # убираем статус и все rt:* через scan (размер семейства минимален)
        pipe = r.pipeline()
        pipe.delete(f"sess:{prev}:status")
        # удалить все rt ключи
        async for key in r.scan_iter(f"sess:{prev}:rt:*"):
            pipe.delete(key)
        await pipe.execute()

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
    resp.delete_cookie(
        key=REFRESH_COOKIE,
        path=COOKIE_PATH,
        domain=settings.DOMAIN,
    )

async def new_login_session(resp: Response, *, user_id: int, role: str) -> str:
    r = build_redis()
    await _revoke_old_session(r, user_id)
    # создаём новый sid
    import uuid
    sid = uuid.uuid4().hex
    await r.setex(f"user:{user_id}:session", _refresh_ttl(), sid)
    await r.setex(f"sess:{sid}:status", _refresh_ttl(), 1)
    # первый refresh
    rt, jti = create_refresh_token(sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await r.setex(f"sess:{sid}:rt:{jti}", _refresh_ttl(), 1)
    await _set_refresh_cookie(resp, rt)
    return sid

async def issue_access_token(*, user_id: int, role: str, sid: str) -> str:
    return create_access_token(sub=user_id, role=role, sid=sid, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> tuple[int, str] | None:
    """
    Возвращает (user_id, new_access_token) и ставит новый refresh-cookie, если всё валидно.
    Иначе None.
    """
    try:
        payload = decode_token(raw_refresh_jwt)
    except Exception:
        return None
    if payload.get("typ") != "refresh":
        return None
    user_id = int(payload.get("sub"))
    sid = payload.get("sid")
    jti = payload.get("jti")
    if not sid or not jti:
        return None

    r = build_redis()
    # single-session проверка
    current_sid = await r.get(f"user:{user_id}:session")
    if current_sid != sid:
        return None
    # валидность конкретного refresh
    if not await r.exists(f"sess:{sid}:rt:{jti}"):
        return None

    # ротация: гасим старый jti, выдаём новый
    await r.delete(f"sess:{sid}:rt:{jti}")
    new_rt, new_jti = create_refresh_token(sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await r.setex(f"sess:{sid}:rt:{new_jti}", _refresh_ttl(), 1)
    await _set_refresh_cookie(resp, new_rt)

    # продлеваем TTL для sid-маркеров
    await r.expire(f"user:{user_id}:session", _refresh_ttl())
    await r.expire(f"sess:{sid}:status", _refresh_ttl())

    # новый access
    role = payload.get("role") or "user"  # роли в refresh нет; роль берём из БД в роутере при необходимости
    access = create_access_token(sub=user_id, role=role, sid=sid, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return user_id, access

async def logout(resp: Response, *, user_id: int):
    r = build_redis()
    sid = await r.get(f"user:{user_id}:session")
    if sid:
        pipe = r.pipeline()
        pipe.delete(f"user:{user_id}:session")
        pipe.delete(f"sess:{sid}:status")
        async for key in r.scan_iter(f"sess:{sid}:rt:*"):
            pipe.delete(key)
        await pipe.execute()
    await _clear_refresh_cookie(resp)
