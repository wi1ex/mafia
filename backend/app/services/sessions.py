from __future__ import annotations
import uuid
from fastapi import Response
from ..settings import settings
from ..core.security import create_access_token, create_refresh_token, decode_token

REFRESH_COOKIE = "rt"
COOKIE_PATH = "/api"

def _refresh_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600

def _set_refresh_cookie(resp: Response, token: str):
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

def _clear_refresh_cookie(resp: Response):
    resp.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH, domain=settings.DOMAIN)

# БЕЗ single-session и БЕЗ Redis
async def new_login_session(resp: Response, *, user_id: int, role: str) -> str:
    sid = uuid.uuid4().hex  # просто включаем в JWT, нигде не храним
    rt, _jti = create_refresh_token(
        sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    _set_refresh_cookie(resp, rt)
    return sid

def issue_access_token(*, user_id: int, role: str, sid: str) -> str:
    return create_access_token(
        sub=user_id, role=role, sid=sid, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

# Stateless-ротация refresh: проверили подпись — выдали новый cookie
async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> bool:
    try:
        payload = decode_token(raw_refresh_jwt)
        if payload.get("typ") != "refresh":
            return False
        user_id = int(payload.get("sub") or 0)
        sid = payload.get("sid")
        if not user_id or not sid:
            return False
    except Exception:
        return False

    new_rt, _ = create_refresh_token(
        sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    _set_refresh_cookie(resp, new_rt)
    return True

async def logout(resp: Response, *, user_id: int):
    # Ничего не инвалидируем, просто убираем refresh-cookie
    _clear_refresh_cookie(resp)
