from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from ..db import SessionLocal
from ..models.room import Room
from ..core.clients import get_redis

router = APIRouter()

async def snapshot(r):
    async with SessionLocal() as db:
        res = await db.execute(select(Room))
        rooms = res.scalars().all()
    pipe = r.pipeline()
    for rm in rooms:
        await pipe.scard(f"room:{rm.id}:members")
    occs = await pipe.execute()
    out = []
    for rm, occ in zip(rooms, occs):
        out.append({"type": "room_snapshot", "payload": {
            "id": rm.id, "title": rm.title, "user_limit": rm.user_limit, "is_private": rm.is_private,
            "created_by_user_id": rm.created_by_user_id, "created_at": str(rm.created_at),
            "updated_at": str(rm.updated_at),
            "occupancy": int(occ or 0),
        }})
    return out


@router.get("/rooms")
async def rooms_stream():
    r = get_redis()

    async def gen():
        # мгновенный слепок
        snap = await snapshot(r)
        for item in snap:
            yield {"event": "update", "data": json.dumps(item)}
        pubsub = r.pubsub()
        await pubsub.subscribe("rooms:events")
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg and msg.get("type") == "message":
                    payload = msg["data"] if isinstance(msg["data"], str) else msg["data"].decode()
                    yield {"event": "update", "data": payload}
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe("rooms:events")
            await pubsub.close()

    return EventSourceResponse(gen(), media_type="text/event-stream")
