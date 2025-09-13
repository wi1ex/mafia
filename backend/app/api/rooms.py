from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any
from ..db import SessionLocal, get_session
from ..models.room import Room
from ..models.user import User
from ..core.logging import log_action
from ..services.livekit_tokens import make_livekit_token
from ..core.clients import get_redis
from ..settings import settings
from ..services.sessions import get_current_user
from ..schemas import RoomCreateIn, RoomOut, Ok
from ..core.route_utils import log_route


router = APIRouter()


def _to_redis_mapping(d: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out


def _serialize(room: Room, *, occupancy: int) -> dict:
    data = {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": room.is_private,
        "creator": room.creator,
        "created_at": room.created_at.isoformat(),
        "updated_at": room.updated_at.isoformat(),
        "occupancy": occupancy,
    }
    return _to_redis_mapping(data)


@log_route("rooms.create")
@router.post("", status_code=201, response_model=RoomOut)
async def create_room(body: RoomCreateIn, db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)) -> RoomOut:
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="title empty")

    room = Room(
        title=title,
        user_limit=body.user_limit,
        is_private=body.is_private,
        creator=current_user.id,
    )
    db.add(room)
    await db.flush()
    await db.refresh(room)

    r = get_redis()
    data = _serialize(room, occupancy=0)
    await r.hset(f"room:{room.id}:params", mapping=data)
    await r.sadd("rooms:index", room.id)
    await db.commit()

    await log_action(db, user_id=current_user.id, username=current_user.username, action="room_created",
                     details={
                         "user_id": current_user.id,
                         "username": current_user.username,
                         "room_id": room.id,
                     })
    await r.publish("rooms:events", json.dumps({"type": "room_created", "payload": data}))

    return RoomOut(
        id=room.id,
        title=room.title,
        user_limit=room.user_limit,
        is_private=room.is_private,
        creator=room.creator,
        created_at=room.created_at.isoformat(),
        updated_at=room.updated_at.isoformat(),
        occupancy=0,
    )


@log_route("rooms.join")
@router.post("/{room_id}/join", response_model=dict)
async def join_room(room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    r = get_redis()
    rm = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if not rm:
        raise HTTPException(status_code=404, detail="room not found")

    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    if occ >= rm.user_limit:
        raise HTTPException(status_code=409, detail="room full")

    await r.sadd(f"room:{room_id}:members", current_user.id)
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    data = _serialize(rm, occupancy=occ)
    await r.hset(f"room:{rm.id}:params", mapping=data)
    await r.sadd("rooms:index", rm.id)
    await r.publish("rooms:events", json.dumps({"type": "occupancy", "payload": {"id": room_id, "occupancy": occ}}))

    return {
        "ws_url": f"wss://{settings.DOMAIN}",
        "token": make_livekit_token(identity=str(current_user.id), name=current_user.username or f"user-{current_user.id}", room=str(room_id)),
        "room_id": room_id,
    }


@log_route("rooms.leave")
@router.post("/{room_id}/leave", response_model=Ok)
async def leave_room(room_id: int = Path(..., ge=1), current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    await r.srem(f"room:{room_id}:members", current_user.id)
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await r.publish("rooms:events", json.dumps({"type": "occupancy", "payload": {"id": room_id, "occupancy": occ}}))
    empty = bool(await r.exists(f"room:{room_id}:empty_probe"))
    if occ == 0 and not empty:
        await r.setex(f"room:{room_id}:empty_probe", 12, "1")

        async def _delayed_cleanup():
            await asyncio.sleep(10)
            if (await r.scard(f"room:{room_id}:members")) == 0:
                async with SessionLocal() as s:
                    rm2 = (await s.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
                    if rm2:
                        await s.delete(rm2)
                        await log_action(s, user_id=current_user.id, username=current_user.username, action="room_deleted",
                                         details={
                                             "user_id": current_user.id,
                                             "username": current_user.username,
                                             "room_id": room_id,
                                         })
                        await s.commit()
                await r.delete(f"room:{room_id}:members")
                await r.delete(f"room:{room_id}:params")
                await r.srem("rooms:index", room_id)
                await r.publish("rooms:events", json.dumps({"type": "room_deleted", "payload": {"id": room_id}}))

        asyncio.create_task(_delayed_cleanup())
    return Ok()
