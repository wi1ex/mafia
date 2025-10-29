from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..utils import emit_rooms_upsert
from ...core.clients import get_redis
from ...core.decorators import log_route, rate_limited, require_room_creator
from ...core.logging import log_action
from ...core.security import get_identity
from ...core.db import get_session
from ...models.room import Room
from ...models.user import User
from ...models.notif import Notif
from ...realtime.sio import sio
from ...realtime.utils import gc_empty_room, get_room_brief
from ...schemas.common import Identity, Ok
from ...schemas.realtime import RoomListItem
from ...schemas.room import RoomIdOut, RoomCreateIn, RoomInfoOut, RoomInfoMemberOut, RoomAccessOut
from ...schemas.user import UserOut

router = APIRouter()


@log_route("rooms.create_room")
@rate_limited(lambda ident, **_: f"rl:create_room:{ident['id']}", limit=5, window_s=60)
@router.post("", response_model=RoomIdOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), ident: Identity = Depends(get_identity)) -> RoomIdOut:
    uid = int(ident["id"])
    creator_name = ident["username"]
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_empty")

    r = get_redis()
    total = int(await r.zcard("rooms:index") or 0)
    if total >= 100:
        raise HTTPException(status_code=409, detail="rooms_limit_global")

    mine = int(await r.scard(f"user:{uid}:rooms") or 0)
    if mine >= 3:
        raise HTTPException(status_code=409, detail="rooms_limit_user")

    room = Room(title=title, user_limit=payload.user_limit, privacy=payload.privacy, creator=uid, creator_name=creator_name)
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
        "privacy": payload.privacy,
    }

    async with r.pipeline() as p:
        await p.hset(f"room:{room.id}:params", mapping=data)
        await p.zadd("rooms:index", {str(room.id): int(room.created_at.timestamp())})
        await p.sadd(f"user:{uid}:rooms", str(room.id))
        await p.set(f"room:{room.id}:empty_since", int(room.created_at.timestamp()), ex=3600*24*30)
        await p.execute()

    await emit_rooms_upsert(room.id)

    async def _gc_soon(rid: int) -> None:
        await asyncio.sleep(12)
        removed = await gc_empty_room(rid)
        if removed:
            await sio.emit("rooms_remove",
                           {"id": rid},
                           namespace="/rooms")

    asyncio.create_task(_gc_soon(room.id))

    await log_action(
        session,
        user_id=uid,
        username=creator_name,
        action="room_created",
        details=f"Создание комнаты room_id={room.id} title={room.title} user_limit={room.user_limit} privacy={payload.privacy}",
    )

    return RoomIdOut(id=room.id)


@log_route("rooms.room_info")
@router.get("/{room_id}/info", response_model=RoomInfoOut, response_model_exclude_none=True)
async def room_info(room_id: int, session: AsyncSession = Depends(get_session)) -> RoomInfoOut:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    order_raw = await r.zrange(f"room:{room_id}:positions", 0, -1)
    order_ids = [int(uid) for uid in order_raw]

    users_map: dict[int, User] = {}
    if order_ids:
        rows = await session.execute(select(User).where(User.id.in_(order_ids)))
        for u in rows.scalars().all():
            users_map[int(u.id)] = u

    members: list[RoomInfoMemberOut] = []
    for uid in order_ids:
        u = users_map.get(uid)
        members.append(RoomInfoMemberOut(id=uid, username=(u.username if u else None), avatar_name=(u.avatar_name if u else None)))

    return RoomInfoOut(members=members)


@log_route("rooms.brief")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:brief:{ident['id']}:{room_id}", limit=5, window_s=1)
@router.get("/{room_id}/brief", response_model=RoomListItem)
async def brief_one(room_id: int) -> RoomListItem:
    r = get_redis()
    data = await get_room_brief(r, room_id)
    if not data:
        raise HTTPException(status_code=404, detail="room_not_found")

    return RoomListItem(**data)


@log_route("rooms.access")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:access:{ident['id']}:{room_id}", limit=5, window_s=1)
@router.get("/{room_id}/access", response_model=RoomAccessOut)
async def access(room_id: int, ident: Identity = Depends(get_identity)) -> RoomAccessOut:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    privacy = (params.get("privacy") or "open").strip()
    if privacy != "private":
        return RoomAccessOut(access="approved")

    uid = int(ident["id"])
    if int(params.get("creator") or 0) == uid:
        return RoomAccessOut(access="approved")

    if await r.sismember(f"room:{room_id}:allow", str(uid)):
        return RoomAccessOut(access="approved")

    if await r.sismember(f"room:{room_id}:pending", str(uid)):
        return RoomAccessOut(access="pending")

    return RoomAccessOut(access="none")


@log_route("rooms.apply")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:apply:{ident['id']}:{room_id}", limit=5, window_s=1)
@router.post("/{room_id}/apply", response_model=Ok, status_code=202)
async def apply(room_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    if (params.get("privacy") or "open") != "private":
        raise HTTPException(status_code=400, detail="not_private")

    uid = int(ident["id"])
    creator = int(params.get("creator") or 0)
    title = (params.get("title") or "").strip()
    if uid == creator:
        return Ok()

    if await r.sismember(f"room:{room_id}:allow", str(uid)):
        return Ok()

    await r.sadd(f"room:{room_id}:pending", str(uid))

    user = await db.get(User, uid)
    try:
        await sio.emit("room_invite",
                       {"room_id": room_id,
                        "room_title": title,
                        "user": {"id": uid, "username": user.username, "avatar_name": user.avatar_name}},
                       room=f"user:{creator}",
                       namespace="/auth")
    except Exception:
        pass

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="room_apply",
        details=f"Подана заявка в комнату room_id={room_id} title={title} creator={creator}",
    )

    return Ok()


@log_route("rooms.list_requests")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:apps_list:{ident['id']}:{room_id}", limit=5, window_s=1)
@require_room_creator("room_id")
@router.get("/{room_id}/requests", response_model=list[UserOut])
async def list_requests(room_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)):
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    if int(params.get("creator") or 0) != int(ident["id"]):
        raise HTTPException(status_code=403, detail="forbidden")

    ids = list(map(int, await r.smembers(f"room:{room_id}:pending") or []))
    if not ids:
        return []

    rows = await db.execute(select(User).where(User.id.in_(ids)))
    return [UserOut(id=u.id, username=u.username, avatar_name=u.avatar_name, role=u.role) for u in rows.scalars().all()]


@log_route("rooms.approve")
@rate_limited(lambda ident, room_id, user_id, **_: f"rl:rooms:approve:{ident['id']}:{room_id}", limit=5, window_s=1)
@require_room_creator("room_id")
@router.post("/{room_id}/requests/{user_id}/approve", response_model=Ok)
async def approve(room_id: int, user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    if int(params.get("creator") or 0) != int(ident["id"]):
        raise HTTPException(status_code=403, detail="forbidden")

    await r.srem(f"room:{room_id}:pending", str(user_id))
    await r.sadd(f"room:{room_id}:allow", str(user_id))

    title = (params.get("title") or "").strip()
    note = Notif(user_id=int(user_id), text=f"Вход в комнату #{room_id}: \"{title}\" одобрен")
    db.add(note)
    await db.commit()
    await db.refresh(note)

    try:
        await sio.emit("notify",
                       {"id": note.id,
                        "text": note.text,
                        "created_at": note.created_at.isoformat()},
                       room=f"user:{user_id}",
                       namespace="/auth")
    except Exception:
        pass

    await log_action(
        db,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="room_approve",
        details=f"Одобрена заявка в комнату room_id={room_id} title={title} target_user={user_id}",
    )

    return Ok()
