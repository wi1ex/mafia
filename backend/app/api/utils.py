from __future__ import annotations
from typing import Any, Dict
from fastapi import HTTPException
from ..core.clients import get_redis
from ..models.room import Room


def to_redis(d: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = v
    return out


def serialize_room(room: Room, *, occupancy: int) -> Dict[str, Any]:
    return {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": room.is_private,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "occupancy": occupancy,
    }


async def rate_limit_create_room(user_id: int, limit: int = 5, window_s: int = 60) -> None:
    r = get_redis()
    key = f"rl:create_room:{user_id}"

    async with r.pipeline(transaction=True) as pipe:
        await pipe.incr(key, 1)
        await pipe.expire(key, window_s)
        cnt, _ = await pipe.execute()

    if int(cnt) > limit:
        raise HTTPException(
            status_code=429,
            detail="rate_limited_create_room",
            headers={"Retry-After": str(window_s)},
        )
