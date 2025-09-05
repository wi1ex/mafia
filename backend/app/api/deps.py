from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis
from ..db import get_session
from ..models.user import User
from ..core.security import decode_token
from ..core.redis import build_redis

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    try:
        payload = decode_token(creds.credentials)
        if payload.get("typ") != "access":
            raise ValueError("wrong token type")
        user_id = int(payload.get("sub"))
        sid = payload.get("sid")
        if not sid:
            raise ValueError("no sid")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    # single-session проверка
    r: redis.Redis = build_redis()
    current_sid = await r.get(f"user:{user_id}:session")
    if current_sid != sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session revoked")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user
