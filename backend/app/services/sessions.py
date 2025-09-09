from __future__ import annotations
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
        domain=settings.DOMAIN
    )


async def new_login_session(resp: Response, *, user_id: int, role: str) -> None:
    rt = create_refresh_token(sub=user_id, ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    _set_refresh_cookie(resp, rt)


def issue_access_token(*, user_id: int, role: str) -> str:
    return create_access_token(sub=user_id, role=role, ttl_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


async def rotate_refresh(resp: Response, *, raw_refresh_jwt: str) -> bool:
    try:
        p = decode_token(raw_refresh_jwt)
        if p.get("typ") != "refresh" or not int(p.get("sub") or 0):
            return False
    except Exception:
        return False
    _set_refresh_cookie(resp, create_refresh_token(sub=int(p["sub"]), ttl_days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
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
