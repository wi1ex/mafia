from __future__ import annotations
import secrets
import structlog
from fastapi import Response
from ..core.clients import get_redis
from ..security.auth_tokens import create_access_token, create_refresh_token, parse_refresh_token
from ..realtime.sio import sio
from ..core.settings import settings

log = structlog.get_logger()


def _set_refresh_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key="rt",
        value=token,
        max_age=settings.REFRESH_EXP_DAY * 86400,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/api",
        domain=settings.DOMAIN
    )


async def new_login_session(resp: Response, *, user_id: int, username: str, role: str) -> tuple[str, str]:
    try:
        r = get_redis()
        sid = secrets.token_urlsafe(16)
        jti = secrets.token_urlsafe(16)

        rt = create_refresh_token(sub=user_id, sid=sid, jti=jti, ttl_days=settings.REFRESH_EXP_DAY)
        prev_sid = await r.get(f"user:{user_id}:sid")
        async with r.pipeline() as p:
            await p.setex(f"session:{sid}:rjti", settings.REFRESH_EXP_DAY * 86400, jti)
            await p.set(f"user:{user_id}:sid", sid)
            if prev_sid and prev_sid != sid:
                await p.delete(f"session:{prev_sid}:rjti")
            await p.execute()

        _set_refresh_cookie(resp, rt)
        at = create_access_token(sub=user_id, username=username, role=role, sid=sid, ttl_minutes=settings.ACCESS_EXP_MIN)

        if prev_sid and prev_sid != sid:
            try:
                await sio.emit("force_logout",
                               {"reason": "replaced"},
                               room=f"user:{user_id}",
                               namespace="/auth")
                await sio.emit("force_logout",
                               {"reason": "replaced"},
                               room=f"user:{user_id}",
                               namespace="/room")
            except Exception:
                log.warning("session.force_logout.emit_failed", user_id=user_id)
        return at, sid

    except Exception:
        log.exception("session.login.db_update_failed", user_id=user_id)
        raise


async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> tuple[bool, int, str | None]:
    r = get_redis()
    ok, uid, sid, jti = parse_refresh_token(raw_refresh_jwt)
    if not ok:
        return False, 0, None

    current_sid = await r.get(f"user:{uid}:sid")
    if not current_sid or current_sid != sid:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.not_current", user_id=uid, sid=sid, current=current_sid)
        return False, 0, None

    current = await r.get(f"session:{sid}:rjti")
    if current is None or current != jti:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.reuse", user_id=uid, sid=sid)
        return False, 0, None

    new_jti = secrets.token_urlsafe(16)
    rt = create_refresh_token(sub=uid, sid=sid, jti=new_jti, ttl_days=settings.REFRESH_EXP_DAY)
    await r.setex(f"session:{sid}:rjti", settings.REFRESH_EXP_DAY * 86400, new_jti)
    _set_refresh_cookie(resp, rt)
    return True, uid, sid


async def logout(resp: Response, *, user_id: int, sid: str | None = None) -> None:
    resp.delete_cookie(key="rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    r = get_redis()
    if sid:
        await r.delete(f"session:{sid}:rjti")
    cur = await r.get(f"user:{user_id}:sid")
    if cur == sid:
        await r.delete(f"user:{user_id}:sid")
