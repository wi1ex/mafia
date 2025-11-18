from __future__ import annotations
import asyncio
from sqlalchemy import select
from contextlib import suppress
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from ..utils import emit_rooms_upsert, serialize_game_for_redis, game_from_redis_to_model
from ...core.clients import get_redis
from ...core.decorators import log_route, rate_limited, require_room_creator
from ...core.logging import log_action
from ...core.security import get_identity
from ...core.db import get_session
from ...models.room import Room
from ...models.user import User
from ...models.notif import Notif
from ...realtime.sio import sio
from ...realtime.utils import gc_empty_room, get_profiles_snapshot
from ...schemas.common import Identity, Ok
from ...schemas.room import RoomIdOut, RoomCreateIn, RoomInfoOut, RoomInfoMemberOut, RoomAccessOut, GameParams
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

    gp = payload.game or GameParams()
    game_dict = {"mode": gp.mode,
                 "format": gp.format,
                 "spectators_limit": int(gp.spectators_limit),
                 "vote_at_zero": bool(gp.vote_at_zero),
                 "vote_three": bool(gp.vote_three),
                 "speech30_at_3_fouls": bool(gp.speech30_at_3_fouls),
                 "extra30_at_2_fouls": bool(gp.extra30_at_2_fouls)}

    room = Room(title=title,
                user_limit=payload.user_limit,
                privacy=payload.privacy,
                creator=uid,
                creator_name=creator_name,
                game=game_dict)
    session.add(room)
    await session.commit()
    await session.refresh(room)

    u = await session.get(User, uid)
    params_data = {
        "id": room.id,
        "title": room.title,
        "user_limit": room.user_limit,
        "creator": room.creator,
        "creator_name": creator_name,
        "creator_avatar_name": u.avatar_name if u else None,
        "created_at": room.created_at.isoformat(),
        "privacy": payload.privacy,
    }
    game_data = serialize_game_for_redis(game_dict)
    params_clean = {k: v for k, v in params_data.items() if v is not None}

    async with r.pipeline() as p:
        await p.hset(f"room:{room.id}:params", mapping=params_clean)
        await p.hset(f"room:{room.id}:game", mapping=game_data)
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
async def room_info(room_id: int) -> RoomInfoOut:
    r = get_redis()
    params = await r.hgetall(f"room:{room_id}:params")
    if not params:
        raise HTTPException(status_code=404, detail="room_not_found")

    order_raw = await r.zrange(f"room:{room_id}:positions", 0, -1)
    order_ids = [int(uid) for uid in order_raw]
    owner_raw = await r.get(f"room:{room_id}:screen_owner")
    screen_owner = int(owner_raw) if owner_raw else 0

    profiles = await get_profiles_snapshot(r, room_id)
    members: list[RoomInfoMemberOut] = []
    for uid in order_ids:
        p = profiles.get(str(uid)) or {}
        members.append(
            RoomInfoMemberOut(
                id=uid,
                username=p.get("username"),
                avatar_name=p.get("avatar_name"),
                screen=(True if screen_owner and uid == screen_owner else None),
            )
        )

    raw_game = await r.hgetall(f"room:{room_id}:game")
    game = game_from_redis_to_model(raw_game)
    
    return RoomInfoOut(members=members, game=game)


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
    with suppress(Exception):
        await sio.emit("room_invite",
                       {"room_id": room_id,
                        "room_title": title,
                        "user": {"id": uid, "username": user.username, "avatar_name": user.avatar_name}},
                       room=f"user:{creator}",
                       namespace="/auth")

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="room_apply",
        details=f"Подача заявки в комнату room_id={room_id} title={title} creator={creator}",
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

    async with r.pipeline(transaction=True) as p:
        await p.srem(f"room:{room_id}:pending", str(user_id))
        await p.sadd(f"room:{room_id}:allow", str(user_id))
        res = await p.execute()

    added = int(res[1] or 0)
    if added == 0:
        return Ok()

    title_room = (params.get("title") or "").strip()
    note = Notif(user_id=int(user_id), title="Заявка одобрена", text=f"Вход в «{title_room}» разрешен")
    db.add(note)
    await db.commit()
    await db.refresh(note)

    with suppress(Exception):
        await sio.emit("notify",
                       {"id": note.id,
                        "title": note.title,
                        "text": note.text,
                        "date": note.created_at.isoformat(),
                        "kind": "approve",
                        "room_id": room_id,
                        "action": {"kind": "route", "label": "Перейти", "to": f"/room/{room_id}"},
                        "ttl_ms": 10000,
                        "read": False},
                       room=f"user:{user_id}",
                       namespace="/auth")
        await sio.emit("room_app_approved",
                       {"room_id": room_id, "user_id": user_id},
                       room=f"user:{int(ident['id'])}",
                       namespace="/auth")

    await log_action(
        db,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="room_approve",
        details=f"Одобрена заявка в комнату room_id={room_id} title={title_room} target_user={user_id}",
    )

    return Ok()
