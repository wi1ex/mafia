from __future__ import annotations
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session
from ..models.room import Room
from ..models.user import User
from ..core.clients import get_redis
from ..realtime.sio import sio
from ..services.sessions import get_current_user
from ..services.livekit_tokens import make_livekit_token
from ..schemas import RoomCreateIn, RoomOut, Ok


router = APIRouter()


def _serialize_room(rm: Room, *, occupancy: int) -> Dict[str, Any]:
    return {
        "id": rm.id,
        "title": rm.title,
        "user_limit": rm.user_limit,
        "is_private": rm.is_private,
        "creator": rm.creator,
        "created_at": rm.created_at.isoformat(),
        "occupancy": occupancy,
    }


@router.get("", response_model=List[RoomOut])
async def list_rooms(session: AsyncSession = Depends(get_session)) -> List[RoomOut]:
    r = get_redis()
    rows = (await session.execute(select(Room))).scalars().all()
    out: List[RoomOut] = []
    for rm in rows:
        occ = int(await r.scard(f"room:{rm.id}:members") or 0)
        data = _serialize_room(rm, occupancy=occ)
        await r.hset(f"room:{rm.id}:params", mapping=data)
        await r.sadd("rooms:index", rm.id)
        out.append(RoomOut(**data))
    return out


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> RoomOut:
    rm = Room(title=payload.title, user_limit=payload.user_limit, is_private=payload.is_private, creator=user.id)
    session.add(rm)
    await session.flush()
    r = get_redis()
    data = _serialize_room(rm, occupancy=0)
    await r.hset(f"room:{rm.id}:params", mapping=data)
    await r.sadd("rooms:index", rm.id)
    return RoomOut(**data)


class JoinOut(RoomOut):
    token: str
    room_id: int
    snapshot: Dict[str, Dict[str, str]]
    self_pref: Dict[str, str]


@router.post("/{room_id}/join", response_model=JoinOut)
async def join_room(room_id: int = Path(..., ge=1), session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)) -> JoinOut:
    rm = await session.get(Room, room_id)
    if not rm:
        raise HTTPException(status_code=404, detail="room_not_found")

    r = get_redis()
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    if occ >= rm.user_limit:
        raise HTTPException(status_code=409, detail="room_is_full")

    await r.sadd(f"room:{room_id}:members", user.id)
    await r.set(f"room:{room_id}:member:{user.id}", str(int(time.time())))

    ids = await r.smembers(f"room:{room_id}:members")
    snapshot: Dict[str, Dict[str, str]] = {}
    for b in ids or []:
        uid = (b.decode() if isinstance(b, (bytes, bytearray)) else str(b))
        st = await r.hgetall(f"room:{room_id}:user:{uid}:state")
        snapshot[uid] = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                         for k, v in (st or {}).items()}
    self_pref_raw = await r.hgetall(f"user:{user.id}:last_state")
    self_pref = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (v.decode() if isinstance(v, (bytes, bytearray)) else v)
                 for k, v in (self_pref_raw or {}).items()}

    lk_token = make_livekit_token(identity=str(user.id), name=user.username or f"user-{user.id}", room=str(room_id))
    data = _serialize_room(rm, occupancy=int(await r.scard(f"room:{room_id}:members") or 0))
    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": data["occupancy"]})
    return JoinOut(**data, token=lk_token, room_id=room_id, snapshot=snapshot, self_pref=self_pref or {})


@router.post("/{room_id}/state", response_model=Ok)
async def update_state(payload: Dict[str, Any], room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    norm = {k: "1" if bool(v) else "0" for k, v in (payload or {}).items() if k in {"mic", "cam", "speakers", "visibility"}}
    if norm:
        await r.hset(f"room:{room_id}:user:{user.id}:state", mapping=norm)
        await r.hset(f"user:{user.id}:last_state", mapping=norm)
    return Ok()


@router.post("/{room_id}/leave", response_model=Ok)
async def leave_room(room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)) -> Ok:
    r = get_redis()
    await r.srem(f"room:{room_id}:members", user.id)
    await r.delete(f"room:{room_id}:member:{user.id}")
    await r.delete(f"room:{room_id}:user:{user.id}:state")
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await sio.emit("rooms_occupancy", {"id": room_id, "occupancy": occ})
    return Ok()
