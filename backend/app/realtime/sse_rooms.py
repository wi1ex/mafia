from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from ..db import SessionLocal
from ..models.room import Room
from ..core.clients import get_redis


router = APIRouter()


async def snapshot():
    r = get_redis()
    async with SessionLocal() as db:
        rooms = (await db.execute(select(Room))).scalars().all()
    pipe = r.pipeline()
    for rm in rooms:
        await pipe.scard(f"room:{rm.id}:members")
    occs = await pipe.execute()
    return [json.dumps({"type": "room_snapshot",
                        "payload": {
                            "id": rm.id,
                            "title": rm.title,
                            "user_limit": rm.user_limit,
                            "is_private": rm.is_private,
                            "created_by_user_id": rm.created_by_user_id,
                            "created_at": str(rm.created_at),
                            "updated_at": str(rm.updated_at),
                            "occupancy": int(o or 0)
                        }}) for rm, o in zip(rooms, occs)]


@router.get("/rooms")
async def rooms_stream():
    r = get_redis()

    async def gen():
        for item in await snapshot():
            yield {"event": "update", "data": item}
        pubsub = r.pubsub()
        await pubsub.subscribe("rooms:events")
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                if msg and msg.get("type") == "message":
                    data = msg["data"]
                    yield {"event": "update", "data": data if isinstance(data, str) else data.decode()}
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe("rooms:events")
            await pubsub.close()

    return EventSourceResponse(gen())
