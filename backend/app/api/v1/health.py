from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from ...db import get_session
from ...core.redis import build_redis

router = APIRouter()


@router.get("/ping")
async def ping(
    db: AsyncSession = Depends(get_session),
):
    await db.execute(text("select 1"))
    r: redis.Redis = build_redis()
    await r.ping()
    return {"status": "ok"}
