from __future__ import annotations
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from ...utils_common import to_redis
from ..utils_api import rate_limit
from ...core.clients import get_redis
from ...core.route_utils import log_route
from ...db import get_session
from ...models.room import Room
from ...models.user import User
from ...realtime.sio import sio
from ...schemas import RoomCreateIn, RoomOut, Identity
from ...services.sessions import get_identity
from ...core.logging import log_action

router = APIRouter()


@log_route("rooms.create_room")
@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), ident: Identity = Depends(get_identity)) -> RoomOut:
    await rate_limit(f"rl:create_room:{ident['id']}", limit=5, window_s=60)

    room = Room(title=payload.title.strip(), user_limit=payload.user_limit, creator=ident["id"])
    session.add(room)
    await session.commit()
    await session.refresh(room)

    creator = await session.get(User, ident["id"])
    creator_name = (creator.username if creator and creator.username else f"user{ident['id']}")
    await log_action(
        session,
        user_id=ident["id"],
        username=creator_name,
        action="room_created",
        details=f"Создание комнаты room_id={room.id} title={room.title} user_limit={room.user_limit}",
    )

    r = get_redis()
    data = {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "occupancy": 0,
    }

    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(f"room:{room.id}:params", mapping=to_redis(data))
        await pipe.zadd("rooms:index", {str(room.id): int(room.created_at.timestamp())})
        await pipe.execute()

    await sio.emit("rooms_upsert", data, namespace="/rooms")
    await sio.emit("rooms_occupancy", {"id": room.id, "occupancy": 0}, namespace="/rooms")

    return RoomOut(**data)
