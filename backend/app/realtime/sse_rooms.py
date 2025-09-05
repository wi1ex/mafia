from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db import get_session
from ..models.room import Room
from ..core.redis import build_redis

router = APIRouter()

async def snapshot(db: AsyncSession, r: redis.Redis):
    res = await db.execute(select(Room))
    rooms = res.scalars().all()
    out = []
    for rm in rooms:
        occ = await r.scard(f"room:{rm.id}:members")
        out.append({
            "id": rm.id,
            "title": rm.title,
            "user_limit": rm.user_limit,
            "is_private": rm.is_private,
            "created_by_user_id": rm.created_by_user_id,
            "created_at": str(rm.created_at),
            "updated_at": str(rm.updated_at),
            "occupancy": int(occ or 0),
        })
    return out

@router.get("/rooms")
async def rooms_stream(db: AsyncSession = Depends(get_session)):
    r = build_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("rooms:events")

    async def gen():
        # initial snapshot
        data = await snapshot(db, r)
        yield {"event": "snapshot", "data": json.dumps(data)}
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg and msg.get("type") == "message":
                    payload = msg["data"]
                    yield {"event": "update", "data": payload}
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
        finally:
            try:
                await pubsub.unsubscribe("rooms:events")
            finally:
                await pubsub.close()

    return EventSourceResponse(gen(), media_type="text/event-stream")
