from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.security import create_access_token, create_refresh_token, decode_token
from ..db import get_session
from ..models.user import User
from ..settings import settings

REFRESH_COOKIE = "rt"
COOKIE_PATH = "/api"

bearer = HTTPBearer(auto_error=False)
_unauth = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def _set_refresh_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        secure=True,
        httponly=True,
        samesite="strict",
        path=COOKIE_PATH,
        domain=settings.DOMAIN,
    )


def issue_access_token(*, user_id: int, role: str, sid: str) -> str:
    return create_access_token(sub=user_id, role=role, sid=sid, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


async def new_login_session(resp: Response, *, user_id: int, role: str) -> str:
    sid = uuid.uuid4().hex
    rt, _ = create_refresh_token(sub=user_id, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    _set_refresh_cookie(resp, rt)
    return sid


async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> bool:
    try:
        p = decode_token(raw_refresh_jwt)
        if p.get("typ") != "refresh":
            return False
        uid = int(p.get("sub") or 0)
        sid = p.get("sid")
        if not uid or not sid:
            return False
    except Exception:
        return False
    rt, _ = create_refresh_token(sub=uid, sid=sid, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    _set_refresh_cookie(resp, rt)
    return True


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_session)) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        raise _unauth
    try:
        p = decode_token(creds.credentials)
        if p.get("typ") != "access":
            raise ValueError
        uid = int(p.get("sub") or 0)
        if not uid:
            raise ValueError
    except Exception:
        raise _unauth
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if not user:
        raise _unauth
    return user


async def logout(resp: Response, *, user_id: int) -> None:
    resp.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH, domain=settings.DOMAIN)
