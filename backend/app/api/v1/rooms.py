from __future__ import annotations
import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import redis.asyncio as redis
from ...db import get_session
from ...models.room import Room
from ...models.user import User
from ...services.logs import log_action
from ...services.livekit_tokens import make_livekit_token
from ...services.rooms_events import publish_room_event, cache_room_params, uncache_room
from ...core.clients import get_redis
from ..deps import get_current_user
from ...settings import settings

router = APIRouter()

def k_members(room_id: int) -> str: return f"room:{room_id}:members"
def k_join(room_id: int, user_id: int) -> str: return f"room:{room_id}:join:{user_id}"
def k_empty_probe(room_id: int) -> str: return f"room:{room_id}:empty_probe"

JOIN_LUA = """
local set = KEYS[1]
local uid = ARGV[1]
local limit = tonumber(ARGV[2])
if redis.call('SISMEMBER', set, uid) == 1 then
  return {1, redis.call('SCARD', set)}
end
local size = redis.call('SCARD', set)
if size >= limit then
  return {0, size}
end
redis.call('SADD', set, uid)
return {1, size + 1}
"""

@router.get("")
async def list_rooms(db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(Room))
    rooms = res.scalars().all()
    r: redis.Redis = get_redis()
    out = []
    # pipeline для снижения round-trips
    pipe = r.pipeline()
    for rm in rooms: pipe.scard(k_members(rm.id))
    occs = await pipe.execute()
    for rm, occ in zip(rooms, occs):
        out.append({
            "id": rm.id,
            "title": rm.title,
            "user_limit": rm.user_limit,
            "is_private": rm.is_private,
            "created_by_user_id": rm.created_by_user_id,
            "created_at": str(rm.created_at),
            "updated_at": str(rm.updated_at),
            "occupancy": int(occ or 0),
        })
    return out

@router.post("", status_code=201)
async def create_room(request: Request, db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    body = await request.json()
    title = (body.get("title") or "").strip()
    user_limit = int(body.get("user_limit") or 0)
    is_private = bool(body.get("is_private") or False)
    if not title or user_limit < 2 or user_limit > 32:
        raise HTTPException(status_code=400, detail="bad params")

    room = Room(created_by_user_id=current_user.id, title=title, user_limit=user_limit, is_private=is_private)
    db.add(room)
    await db.flush()

    r: redis.Redis = get_redis()
    await cache_room_params(r, room.id, {
        "title": room.title,
        "user_limit": room.user_limit,
        "is_private": int(room.is_private),
        "created_by": room.created_by_user_id,
        "created_at": str(room.created_at),
    })
    await publish_room_event(r, type_="room_created", payload={
        "id": room.id, "title": room.title, "user_limit": room.user_limit, "is_private": room.is_private, "occupancy": 0
    })
    await log_action(db, user_id=current_user.id, username=current_user.username, action="room_created", details={"room_id": room.id, "title": room.title, "limit": room.user_limit})
    await db.commit()

    return {
        "id": room.id, "title": room.title, "user_limit": room.user_limit, "is_private": room.is_private,
        "created_by_user_id": room.created_by_user_id, "created_at": str(room.created_at), "updated_at": str(room.updated_at),
        "occupancy": 0,
    }

@router.post("/{room_id}/join")
async def join_room(room_id: int = Path(...), db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    res = await db.execute(select(Room).where(Room.id == room_id))
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="room not found")

    r: redis.Redis = get_redis()
    ok, size = await r.eval(JOIN_LUA, 1, k_members(room_id), current_user.id, room.user_limit)
    if int(ok) != 1:
        raise HTTPException(status_code=403, detail="room_full")

    await r.set(k_join(room_id, current_user.id), int(time.time()), ex=24*3600)
    await publish_room_event(r, type_="occupancy", payload={"id": room_id, "occupancy": int(size)})

    lk_token = make_livekit_token(identity=str(current_user.id), name=current_user.username or str(current_user.id), room=str(room_id), ttl_minutes=60)
    # ВАЖНО: возвращаем корректный wss URL с путём /rtc
    return {"ws_url": f"wss://{settings.DOMAIN}/rtc", "token": lk_token, "room_id": room_id}

@router.post("/{room_id}/leave")
async def leave_room(room_id: int = Path(...), db: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    r: redis.Redis = get_redis()
    await r.srem(k_members(room_id), current_user.id)
    ts = await r.getdel(k_join(room_id, current_user.id))
    if ts:
        res = await db.execute(select(Room).where(Room.id == room_id))
        rm = res.scalar_one_or_none()
        if rm:
            d = dict(rm.user_durations or {})
            uid = str(current_user.id)
            delta = max(0, int(time.time()) - int(ts))
            d[uid] = int(d.get(uid, 0)) + delta
            await db.execute(update(Room).where(Room.id == room_id).values(user_durations=d))
            await db.commit()

    occ = int(await r.scard(k_members(room_id)) or 0)
    await publish_room_event(r, type_="occupancy", payload={"id": room_id, "occupancy": occ})

    if occ == 0 and not await r.exists(k_empty_probe(room_id)):
        await r.setex(k_empty_probe(room_id), 12, "1")
        async def _delayed():
            await asyncio.sleep(10)
            if (await r.scard(k_members(room_id))) == 0:
                res2 = await db.execute(select(Room).where(Room.id == room_id))
                rm2 = res2.scalar_one_or_none()
                if rm2:
                    await db.delete(rm2)
                    await log_action(db, user_id=current_user.id, username=current_user.username, action="room_deleted", details={"room_id": room_id})
                    await db.commit()
                await r.delete(k_members(room_id))
                await uncache_room(r, room_id)
                await publish_room_event(r, type_="room_deleted", payload={"id": room_id})
        asyncio.create_task(_delayed())

    return {"status": "ok"}
