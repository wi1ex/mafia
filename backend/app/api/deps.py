from __future__ import annotations
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as redis
from ..db import get_session
from ..models.user import User
from ..core.security import decode_token
from ..core.clients import get_redis

bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_session),
):
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="no token")

    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload.get("sub"))
        sid = payload.get("sid")
        if not user_id or not sid:
            raise ValueError("bad token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")

    r: redis.Redis = get_redis()
    current_sid = await r.get(f"user:{user_id}:session")
    if current_sid != sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session revoked")

    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user
