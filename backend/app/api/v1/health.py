from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from ...db import get_session
from ...core.clients import get_redis

router = APIRouter()


@router.get("/ping")
async def ping(
    db: AsyncSession = Depends(get_session),
):
    await db.execute(text("select 1"))
    r: redis.Redis = get_redis()
    await r.ping()
    return {"status": "ok"}
