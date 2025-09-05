from __future__ import annotations
import json
import redis.asyncio as redis

CHANNEL = "rooms:events"

async def publish_room_event(r: redis.Redis, *, type_: str, payload: dict):
    await r.publish(CHANNEL, json.dumps({"type": type_, "payload": payload}))

async def cache_room_params(r: redis.Redis, room_id: int, params: dict):
    await r.hset(f"room:{room_id}:params", mapping=params)
    await r.sadd("rooms:index", room_id)

async def uncache_room(r: redis.Redis, room_id: int):
    await r.delete(f"room:{room_id}:params")
    await r.srem("rooms:index", room_id)
