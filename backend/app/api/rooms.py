from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..db import get_session
from ..models.room import Room
from ..models.user import User
from ..core.clients import get_redis
from ..services.livekit_tokens import make_livekit_token
from ..services.sessions import get_current_user
from ..schemas import RoomCreateIn, RoomOut, Ok
from ..settings import settings


router = APIRouter()


def _serialize(rm: Room, *, occupancy: int = 0) -> Dict[str, Any]:
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
    r = await get_redis()
    rows = (await session.execute(select(Room))).scalars().all()
    out: List[RoomOut] = []
    for rm in rows:
        occ = int(await r.scard(f"room:{rm.id}:members") or 0)
        data = _serialize(rm, occupancy=occ)
        out.append(RoomOut(**data))
        await r.hset(f"room:{rm.id}:params", mapping=data)
        await r.sadd("rooms:index", rm.id)
    return out


@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)) -> RoomOut:
    rm = Room(title=payload.title, user_limit=payload.user_limit, is_private=payload.is_private, creator=current_user.id)
    session.add(rm)
    await session.flush()
    r = await get_redis()
    data = _serialize(rm, occupancy=0)
    await r.hset(f"room:{rm.id}:params", mapping=data)
    await r.sadd("rooms:index", rm.id)
    await session.commit()
    return RoomOut(**data)


@router.post("/{room_id}/join", response_model=dict)
async def join_room(room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    r = await get_redis()
    rm = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if not rm:
        raise HTTPException(status_code=404, detail="room not found")

    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    if occ >= rm.user_limit:
        raise HTTPException(status_code=409, detail="room full")

    await r.sadd(f"room:{room_id}:members", current_user.id)
    await r.set(f"room:{room_id}:member:{current_user.id}", str(int(time.time())))

    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    data = _serialize(rm, occupancy=occ)
    await r.hset(f"room:{rm.id}:params", mapping=data)
    await r.sadd("rooms:index", rm.id)
    await r.publish("rooms:events", json.dumps({"type": "occupancy", "payload": {"id": room_id, "occupancy": occ}}))

    members = await r.smembers(f"room:{room_id}:members")
    snapshot: Dict[str, Dict[str, str]] = {}
    for uid_b in members or []:
        uid = uid_b.decode() if isinstance(uid_b, (bytes, bytearray)) else str(uid_b)
        st = await r.hgetall(f"room:{room_id}:user:{uid}:state")
        snapshot[uid] = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (
            v.decode() if isinstance(v, (bytes, bytearray)) else v) for k, v in (st or {}).items()}

    self_pref_raw = await r.hgetall(f"user:{current_user.id}:last_state")
    self_pref = {(k.decode() if isinstance(k, (bytes, bytearray)) else k): (
        v.decode() if isinstance(v, (bytes, bytearray)) else v) for k, v in (self_pref_raw or {}).items()}

    await r.publish(f"room:{room_id}:events", json.dumps(
        {"type": "member_joined", "payload": {"user_id": current_user.id}, "ts": int(time.time())}))

    return {
        "ws_url": f"wss://{settings.DOMAIN}",
        "token": make_livekit_token(identity=str(current_user.id), name=current_user.username or f"user-{current_user.id}", room=str(room_id)),
        "room_id": room_id,
        "state_ws": f"wss://{settings.DOMAIN}/ws/room/{room_id}",
        "snapshot": snapshot,
        "self_pref": self_pref or {},
    }


@router.post("/{room_id}/state", response_model=Ok)
async def update_state(payload: Dict[str, Any], room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user)) -> Ok:
    r = await get_redis()
    norm = {k: "1" if bool(v) else "0" for k, v in payload.items() if k in {"mic", "cam", "speakers", "visibility"}}
    if norm:
        await r.hset(f"room:{room_id}:user:{current_user.id}:state", mapping=norm)
        await r.hset(f"user:{current_user.id}:last_state", mapping=norm)
        await r.publish(f"room:{room_id}:events", json.dumps({"type": "state_changed", "payload": {"user_id": current_user.id, **norm}, "origin": current_user.id, "ts": int(time.time())}))
    return Ok()


@router.post("/{room_id}/heartbeat", response_model=Ok)
async def heartbeat(room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user)) -> Ok:
    r = await get_redis()
    await r.set(f"room:{room_id}:member:{current_user.id}", str(int(time.time())))
    return Ok()


@router.post("/{room_id}/leave", response_model=Ok)
async def leave_room(request: Request, room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user)) -> Ok:
    r = await get_redis()
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        norm = {k: "1" if bool(v) else "0" for k, v in body.items() if k in {"mic", "cam", "speakers", "visibility"}}
        if norm:
            await r.hset(f"user:{current_user.id}:last_state", mapping=norm)

    await r.srem(f"room:{room_id}:members", current_user.id)
    await r.delete(f"room:{room_id}:member:{current_user.id}")
    await r.delete(f"room:{room_id}:user:{current_user.id}:state")

    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await r.publish("rooms:events", json.dumps({"type": "occupancy", "payload": {"id": room_id, "occupancy": occ}}))
    await r.publish(f"room:{room_id}:events", json.dumps({"type": "member_left", "payload": {"user_id": current_user.id}, "ts": int(time.time())}))
    return Ok()
