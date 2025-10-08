from __future__ import annotations
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.clients import get_redis
from ...core.decorators import log_route, rate_limited
from ...core.logging import log_action
from ...core.security import get_identity
from ...db import get_session
from ...models.room import Room
from ...models.user import User
from ...realtime.sio import sio
from ...schemas import RoomCreateIn, RoomOut, Identity
from ...schemas import RoomInfoOut, RoomInfoMemberOut

router = APIRouter()

MAX_ROOMS_GLOBAL = 100
MAX_ROOMS_PER_USER = 3


@log_route("rooms.create_room")
@rate_limited(lambda ident, **_: f"rl:create_room:{ident['id']}", limit=5, window_s=60)
@router.post("", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), ident: Identity = Depends(get_identity)) -> RoomOut:
    uid = int(ident["id"])
    creator_name = ident["username"]
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_empty")

    r = get_redis()
    total = int(await r.zcard("rooms:index") or 0)
    if total >= MAX_ROOMS_GLOBAL:
        raise HTTPException(status_code=409, detail="rooms_limit_global")

    mine = int(await r.scard(f"user:{uid}:rooms") or 0)
    if mine >= MAX_ROOMS_PER_USER:
        raise HTTPException(status_code=409, detail="rooms_limit_user")

    room = Room(title=title, user_limit=payload.user_limit, creator=uid, creator_name=creator_name)
    session.add(room)
    await session.commit()
    await session.refresh(room)

    data = {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "creator": room.creator,
        "creator_name": creator_name,
        "created_at": room.created_at.isoformat(),
        "occupancy": 0,
    }

    async with r.pipeline() as p:
        await p.hset(f"room:{room.id}:params", mapping=data)
        await p.zadd("rooms:index", {str(room.id): int(room.created_at.timestamp())})
        await p.sadd(f"user:{uid}:rooms", str(room.id))
        await p.execute()

    await sio.emit("rooms_upsert",
                   data,
                   namespace="/rooms")
    await sio.emit("rooms_occupancy",
                   {"id": room.id, "occupancy": 0},
                   namespace="/rooms")

    await log_action(
        session,
        user_id=uid,
        username=creator_name,
        action="room_created",
        details=f"Создание комнаты room_id={room.id} title={room.title} user_limit={room.user_limit}",
    )

    return RoomOut(**data)


@log_route("rooms.info")
@router.get("/{room_id}/info", response_model=RoomInfoOut, response_model_exclude_none=True)
async def room_info(room_id: int, session: AsyncSession = Depends(get_session)) -> RoomInfoOut:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    try:
        rid = int(params.get("id") or room_id)
        title = str(params.get("title") or "")
        user_limit = int(params.get("user_limit") or 0)
        creator = int(params.get("creator") or 0)
        creator_name = str(params.get("creator_name") or "")
        created_at = str(params.get("created_at") or "")
    except Exception:
        raise HTTPException(status_code=404, detail="room_not_found")

    occupancy = int(await r.scard(f"room:{rid}:members") or 0)
    order_raw = await r.zrange(f"room:{rid}:positions", 0, -1)
    order_ids = [int(uid) for uid in order_raw]

    users_map: dict[int, User] = {}
    if order_ids:
        rows = await session.execute(select(User).where(User.id.in_(order_ids)))
        for u in rows.scalars().all():
            users_map[int(u.id)] = u

    members: list[RoomInfoMemberOut] = []
    for uid in order_ids:
        u = users_map.get(uid)
        members.append(RoomInfoMemberOut(
            id=uid,
            username=(u.username if u else f"user{uid}"),
            avatar_name=u.avatar_name,
        ))

    return RoomInfoOut(
        id=rid,
        title=title,
        user_limit=user_limit,
        creator=creator,
        creator_name=creator_name,
        created_at=created_at,
        occupancy=occupancy,
        members=members,
    )
