from __future__ import annotations
import asyncio
from typing import Dict
from typing import List
from fastapi import APIRouter, Depends, Path
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils import serialize_room, to_redis, rate_limit_create_room
from ...core.clients import get_redis
from ...core.route_utils import log_route
from ...db import get_session
from ...models.room import Room
from ...models.user import User
from ...realtime.sio import sio
from ...realtime.utils import gc_empty_room
from ...schemas import RoomCreateIn, RoomOut, JoinOut, Ok
from ...services.livekit_tokens import make_livekit_token
from ...services.sessions import get_current_user


router = APIRouter()


@log_route("rooms.list_rooms")
@router.get("", response_model=List[RoomOut])
async def list_rooms(session: AsyncSession = Depends(get_session)) -> List[RoomOut]:
    r = get_redis()
    rooms = (await session.execute(select(Room))).scalars().all()
    pipe = r.pipeline()
    for room in rooms:
        await pipe.scard(f"room:{room.id}:members")
    occs = await pipe.execute()
    out: List[RoomOut] = []
    for room, occ in zip(rooms, occs):
        data = serialize_room(room, occupancy=occ)
        out.append(RoomOut(**data))
    return out


@log_route("rooms.create_room")
@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> RoomOut:
    await rate_limit_create_room(user.id, limit=5, window_s=60)

    room = Room(title=payload.title, user_limit=payload.user_limit, is_private=payload.is_private, creator=user.id)
    session.add(room)
    await session.flush()
    await session.commit()

    r = get_redis()
    data = serialize_room(room, occupancy=0)

    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(f"room:{room.id}:params", mapping=to_redis(data))
        await pipe.sadd("rooms:index", room.id)
        await pipe.execute()

    await sio.emit("rooms_upsert", data, namespace="/rooms")
    await sio.emit("rooms_occupancy", {"id": room.id, "occupancy": 0}, namespace="/rooms")

    return RoomOut(**data)


@log_route("rooms.join_room")
@router.post("/{room_id}/join", response_model=JoinOut)
async def join_room(room_id: int = Path(..., ge=1), session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> JoinOut:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room_not_found")

    r = get_redis()
    is_member = await r.sismember(f"room:{room_id}:members", str(user.id))
    if not is_member:
        occ = int(await r.scard(f"room:{room_id}:members") or 0)
        if occ >= room.user_limit:
            raise HTTPException(status_code=409, detail="room_is_full")
        await r.sadd(f"room:{room_id}:members", user.id)

    ids = await r.smembers(f"room:{room_id}:members")
    snapshot: Dict[str, Dict[str, str]] = {}
    if ids:
        pipe = r.pipeline()
        for uid in ids:
            await pipe.hgetall(f"room:{room_id}:user:{uid}:state")
        states = await pipe.execute()
        for uid, st in zip(ids, states):
            snapshot[str(uid)] = st or {}
    self_pref = snapshot.get(str(user.id), {})

    occ_now = int(await r.scard(f"room:{room_id}:members") or 0)
    lk_token = make_livekit_token(identity=str(user.id), name=user.username or f"user-{user.id}", room=str(room_id))
    data = serialize_room(room, occupancy=occ_now)

    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": occ_now}, namespace="/rooms")
    return JoinOut(**data, token=lk_token, room_id=room_id, snapshot=snapshot, self_pref=self_pref or {})


@log_route("rooms.leave_room")
@router.post("/{room_id}/leave", response_model=Ok)
async def leave_room(room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    await r.srem(f"room:{room_id}:members", user.id)
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": occ}, namespace="/rooms")
    if occ == 0:
        asyncio.create_task(gc_empty_room(room_id))
    return Ok()
