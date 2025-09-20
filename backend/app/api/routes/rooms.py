from __future__ import annotations
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from ...utils import to_redis, rate_limit, rooms_index_add
from ...core.clients import get_redis
from ...core.route_utils import log_route
from ...db import get_session
from ...models.room import Room
from ...models.user import User
from ...realtime.sio import sio
from ...schemas import RoomCreateIn, RoomOut
from ...services.sessions import get_current_user

router = APIRouter()

@log_route("rooms.create_room")
@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> RoomOut:
    await rate_limit(f"rl:create_room:{user.id}", limit=5, window_s=60)

    room = Room(title=payload.title.strip(), user_limit=payload.user_limit, is_private=payload.is_private, creator=user.id)
    session.add(room)
    await session.commit()
    await session.refresh(room)

    r = get_redis()
    data = {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": room.is_private,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "occupancy": 0,
    }

    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(f"room:{room.id}:params", mapping=to_redis(data))
        await pipe.execute()

    await rooms_index_add(r, rid=room.id, created_at_iso=data["created_at"])
    await sio.emit("rooms_upsert", data, namespace="/rooms")
    await sio.emit("rooms_occupancy", {"id": room.id, "occupancy": 0}, namespace="/rooms")

    return RoomOut(**data)
