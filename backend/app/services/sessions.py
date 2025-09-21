from __future__ import annotations
import secrets
import structlog
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import update, func
from ..core.clients import get_redis
from ..core.security import create_access_token, create_refresh_token, decode_token, parse_refresh_token
from ..db import SessionLocal
from ..models.user import User
from ..schemas import Identity
from ..settings import settings

log = structlog.get_logger()

REFRESH_COOKIE = "rt"
COOKIE_PATH = "/api"

bearer = HTTPBearer(auto_error=False)
_unauth = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _set_refresh_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=True,
        httponly=True,
        samesite="strict",
        path=COOKIE_PATH,
        domain=settings.DOMAIN
    )


async def new_login_session(resp: Response, *, user_id: int, role: str) -> str:
    try:
        r = get_redis()
        sid = secrets.token_urlsafe(16)
        jti = secrets.token_urlsafe(16)

        rt = create_refresh_token(sub=user_id, sid=sid, jti=jti, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await r.setex(f"session:{sid}:rjti", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, jti)
        _set_refresh_cookie(resp, rt)
        at = create_access_token(sub=user_id, role=role, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        async with SessionLocal() as db:
            await db.execute(update(User).where(User.id == user_id).values(last_login_at=func.now()))
            await db.commit()

        log.info("session.login", user_id=user_id, role=role, sid=sid)
        return at

    except Exception:
        log.exception("session.login.db_update_failed", user_id=user_id)
        raise


async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> tuple[bool, int, str | None]:
    r = get_redis()
    ok, uid, sid, jti = parse_refresh_token(raw_refresh_jwt)
    if not ok:
        return False, 0, None

    current = await r.get(f"session:{sid}:rjti")
    if current is None or current != jti:
        await logout(resp, user_id=uid, sid=sid)
        log.warning("session.refresh.reuse", user_id=uid, sid=sid)
        return False, 0, None

    new_jti = secrets.token_urlsafe(16)
    rt = create_refresh_token(sub=uid, sid=sid, jti=new_jti, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await r.setex(f"session:{sid}:rjti", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, new_jti)
    _set_refresh_cookie(resp, rt)
    log.debug("session.refresh.rotated", user_id=uid, sid=sid)
    return True, uid, sid


async def get_identity(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> Identity:
    if not creds or creds.scheme.lower() != "bearer":
        raise _unauth
    try:
        p = decode_token(creds.credentials)
        if p.get("typ") != "access":
            raise ValueError
        return {"id": int(p["sub"]), "role": str(p["role"])}
    except Exception:
        raise _unauth


async def logout(resp: Response, *, user_id: int, sid: str | None = None) -> None:
    resp.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH, domain=settings.DOMAIN, samesite="strict")
    r = get_redis()
    if sid:
        await r.delete(f"session:{sid}:rjti")
    log.info("session.logout", user_id=user_id, sid=sid)
