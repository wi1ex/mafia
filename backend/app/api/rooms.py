from __future__ import annotations
import asyncio
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session
from ..models.room import Room
from ..models.user import User
from ..core.clients import get_redis
from ..realtime.sio import sio
from ..realtime.utils import gc_empty_room
from ..services.sessions import get_current_user
from ..services.livekit_tokens import make_livekit_token
from ..schemas import RoomCreateIn, RoomOut, JoinOut, Ok


router = APIRouter()


def _to_redis(d: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = v
    return out


def _serialize_room(room: Room, *, occupancy: int) -> Dict[str, Any]:
    return {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": room.is_private,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "occupancy": occupancy,
    }


@router.get("", response_model=List[RoomOut])
async def list_rooms(session: AsyncSession = Depends(get_session)) -> List[RoomOut]:
    r = get_redis()
    rows = (await session.execute(select(Room))).scalars().all()
    out: List[RoomOut] = []
    for room in rows:
        occ = int(await r.scard(f"room:{room.id}:members") or 0)
        data = _serialize_room(room, occupancy=occ)
        await r.hset(f"room:{room.id}:params", mapping=_to_redis(data))
        await r.sadd("rooms:index", room.id)
        out.append(RoomOut(**data))
    return out


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> RoomOut:
    room = Room(title=payload.title, user_limit=payload.user_limit, is_private=payload.is_private, creator=user.id)
    session.add(room)
    await session.flush()
    await session.commit()

    data = _serialize_room(room, occupancy=0)
    redis_data = _to_redis(data)

    r = get_redis()
    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(f"room:{room.id}:params", mapping=redis_data)
        await pipe.sadd("rooms:index", room.id)
        await pipe.execute()

    await sio.emit("rooms_upsert", data, namespace="/rooms")
    await sio.emit("rooms_occupancy", {"id": room.id, "occupancy": 0}, namespace="/rooms")

    return RoomOut(**data)


@router.post("/{room_id}/join", response_model=JoinOut)
async def join_room(room_id: int = Path(..., ge=1), session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> JoinOut:
    room = await session.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="room_not_found")

    r = get_redis()
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    if occ >= room.user_limit:
        raise HTTPException(status_code=409, detail="room_is_full")

    await r.sadd(f"room:{room_id}:members", user.id)

    ids = await r.smembers(f"room:{room_id}:members")
    snapshot: Dict[str, Dict[str, str]] = {}
    for uid in ids or []:
        snapshot[uid] = await r.hgetall(f"room:{room_id}:user:{uid}:state")

    self_pref = snapshot.get(str(user.id), {})

    lk_token = make_livekit_token(identity=str(user.id), name=user.username or f"user-{user.id}", room=str(room_id))
    data = _serialize_room(room, occupancy=int(await r.scard(f"room:{room_id}:members") or 0))
    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": data["occupancy"]}, namespace="/rooms")
    return JoinOut(**data, token=lk_token, room_id=room_id, snapshot=snapshot, self_pref=self_pref or {})


@router.post("/{room_id}/state", response_model=Ok)
async def update_state(payload: Dict[str, Any], room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    data = {k: "1" if bool(v) else "0" for k, v in (payload or {}).items() if k in {"mic", "cam", "speakers", "visibility"}}
    if data:
        await r.hset(f"room:{room_id}:user:{user.id}:state", mapping=data)
    return Ok()


@router.post("/{room_id}/leave", response_model=Ok)
async def leave_room(room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    await r.srem(f"room:{room_id}:members", user.id)
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": occ}, namespace="/rooms")
    if occ == 0:
        asyncio.create_task(gc_empty_room(room_id))
    return Ok()
