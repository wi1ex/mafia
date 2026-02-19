from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timezone
from time import time
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.clients import get_redis
from ...security.decorators import log_route, rate_limited, require_room_creator
from ...core.logging import log_action
from ...security.auth_tokens import get_identity
from ...core.db import get_session
from ...models.room import Room
from ...models.user import User
from ...models.notif import Notif
from ...realtime.sio import sio
from ...schemas.common import Identity, Ok
from ...schemas.room import (
    RoomIdOut,
    RoomCreateIn,
    RoomInfoOut,
    RoomInfoMemberOut,
    RoomSpectatorsOut,
    RoomSpectatorOut,
    RoomAccessOut,
    RoomRequestOut,
    GameParams,
    RoomBriefOut,
)
from ...security.parameters import get_cached_settings
from ..utils import (
    emit_rooms_upsert,
    serialize_game_for_redis,
    game_from_redis_to_model,
    build_room_members_for_info,
    fetch_user_name_avatar_maps,
    get_room_params_or_404,
    ensure_room_access_allowed,
    schedule_room_gc,
)
from ...realtime.utils import get_rooms_brief, filter_rooms_for_viewer

router = APIRouter()


@log_route("rooms.create_room")
@rate_limited(lambda ident, **_: f"rl:create_room:{ident['id']}", limit=1, window_s=1)
@router.post("", response_model=RoomIdOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateIn, session: AsyncSession = Depends(get_session), ident: Identity = Depends(get_identity)) -> RoomIdOut:
    uid = int(ident["id"])
    creator_name = ident["username"]
    app_settings = get_cached_settings()
    if not app_settings.rooms_can_create:
        raise HTTPException(status_code=403, detail="rooms_create_disabled")

    await ensure_room_access_allowed(session, uid)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=422, detail="title_empty")

    r = get_redis()
    total = int(await r.zcard("rooms:index") or 0)
    if total >= app_settings.rooms_limit_global:
        raise HTTPException(status_code=409, detail="rooms_limit_global")

    mine = int(await r.scard(f"user:{uid}:rooms") or 0)
    if mine >= app_settings.rooms_limit_per_user:
        raise HTTPException(status_code=409, detail="rooms_limit_user")

    gp = payload.game
    game_limit = int(app_settings.game_min_ready_players) + 1
    anonymity = payload.anonymity
    if int(payload.user_limit) == game_limit:
        anonymity = "visible"
    privacy = "private" if anonymity == "hidden" else payload.privacy
    game_dict = {
        "mode": gp.mode,
        "format": gp.format,
        "spectators_limit": int(gp.spectators_limit),
        "nominate_mode": gp.nominate_mode,
        "break_at_zero": bool(gp.break_at_zero),
        "lift_at_zero": bool(gp.lift_at_zero),
        "lift_3x": bool(gp.lift_3x),
        "wink_knock": bool(gp.wink_knock),
        "farewell_wills": bool(gp.farewell_wills),
        "music": bool(gp.music),
    }

    room = Room(
        title=title,
        user_limit=payload.user_limit,
        privacy=privacy,
        anonymity=anonymity,
        creator=uid,
        creator_name=creator_name,
        game=game_dict,
    )
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
        "privacy": privacy,
        "anonymity": anonymity,
        "entry_closed": "0",
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

    schedule_room_gc(room.id)

    await log_action(
        session,
        user_id=uid,
        username=creator_name,
        action="room_created",
        details=f"Создание комнаты room_id={room.id} title={room.title} user_limit={room.user_limit} privacy={privacy} anonymity={anonymity}",
    )

    return RoomIdOut(id=room.id)


@log_route("rooms.active_list")
@rate_limited(lambda ident, **_: f"rl:rooms:active_list:{ident['id']}", limit=5, window_s=1)
@router.get("/active", response_model=list[RoomBriefOut])
async def list_active_rooms(ident: Identity = Depends(get_identity)) -> list[RoomBriefOut]:
    r = get_redis()
    raw_ids = await r.zrange("rooms:index", 0, -1)
    ids: list[int] = []
    for raw in raw_ids or []:
        try:
            rid = int(raw)
        except Exception:
            continue
        if rid > 0:
            ids.append(rid)
    if not ids:
        return []

    items = await get_rooms_brief(r, ids)
    items = await filter_rooms_for_viewer(r, items, str(ident.get("role") or "user"), int(ident.get("id") or 0))
    out: list[RoomBriefOut] = []
    for item in items:
        try:
            out.append(RoomBriefOut(**item))
        except Exception:
            continue

    return out


@log_route("rooms.room_info")
@router.get("/{room_id}/info", response_model=RoomInfoOut, response_model_exclude_none=True)
async def room_info(room_id: int) -> RoomInfoOut:
    r = get_redis()
    await get_room_params_or_404(r, room_id)

    raw_members = await build_room_members_for_info(r, room_id)
    raw_game = await r.hgetall(f"room:{room_id}:game")
    game = game_from_redis_to_model(raw_game)

    members = [
        RoomInfoMemberOut(
            id=m["id"],
            username=m.get("username"),
            avatar_name=m.get("avatar_name"),
            screen=m.get("screen"),
            role=m.get("role"),
            slot=m.get("slot"),
            alive=m.get("alive"),
        )
        for m in raw_members
    ]

    try:
        spectators_count = int(await r.scard(f"room:{room_id}:spectators") or 0)
    except Exception:
        spectators_count = 0

    return RoomInfoOut(members=members, game=game, spectators_count=spectators_count)


@log_route("rooms.spectators")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:spectators:{ident['id']}:{room_id}", limit=10, window_s=1)
@router.get("/{room_id}/spectators", response_model=RoomSpectatorsOut)
async def room_spectators(room_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> RoomSpectatorsOut:
    r = get_redis()
    await get_room_params_or_404(r, room_id)

    try:
        raw_ids = await r.smembers(f"room:{room_id}:spectators")
    except Exception:
        raw_ids = set()

    ids: list[int] = []
    for raw in raw_ids or []:
        try:
            ids.append(int(raw))
        except Exception:
            continue

    if not ids:
        return RoomSpectatorsOut(spectators=[])

    name_map, avatar_map = await fetch_user_name_avatar_maps(session, set(ids))

    join_map: dict[int, int] = {}
    try:
        raw_join = await r.hgetall(f"room:{room_id}:spectators_join")
        for k, v in (raw_join or {}).items():
            try:
                join_map[int(k)] = int(v or 0)
            except Exception:
                continue
    except Exception:
        join_map = {}

    ids.sort(key=lambda uid: (join_map.get(uid, 0), name_map.get(uid) or "", uid))
    spectators = [RoomSpectatorOut(id=uid, username=name_map.get(uid), avatar_name=avatar_map.get(uid)) for uid in ids]

    return RoomSpectatorsOut(spectators=spectators)


@log_route("rooms.update_game")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:update_game:{ident['id']}:{room_id}", limit=5, window_s=1)
@require_room_creator("room_id")
@router.patch("/{room_id}/game", response_model=Ok)
async def update_game(room_id: int, payload: GameParams, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    raw_gstate = await r.hgetall(f"room:{room_id}:game_state")
    phase = str(raw_gstate.get("phase") or "idle")
    if phase != "idle":
        raise HTTPException(status_code=409, detail="game_in_progress")

    game_dict = {
        "mode": payload.mode,
        "format": payload.format,
        "spectators_limit": int(payload.spectators_limit),
        "nominate_mode": payload.nominate_mode,
        "break_at_zero": bool(payload.break_at_zero),
        "lift_at_zero": bool(payload.lift_at_zero),
        "lift_3x": bool(payload.lift_3x),
        "wink_knock": bool(payload.wink_knock),
        "farewell_wills": bool(payload.farewell_wills),
        "music": bool(payload.music),
    }

    room = await session.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="room_not_found")

    old_game = dict(room.game or {})
    changes = []
    for key, new_value in game_dict.items():
        old_value = old_game.get(key)
        if old_value != new_value:
            changes.append(f"{key}: {old_value} -> {new_value}")
    changes_str = "; ".join(changes) if changes else "нет"

    room.game = game_dict
    await session.commit()

    game_data = serialize_game_for_redis(game_dict)
    await r.hset(f"room:{room_id}:game", mapping=game_data)

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="room_game_update",
        details=f"Обновлены параметры игры room_id={room_id} title={params.get('title') or ''} changes={changes_str}",
    )

    return Ok()


@log_route("rooms.access")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:access:{ident['id']}:{room_id}", limit=10, window_s=1)
@router.get("/{room_id}/access", response_model=RoomAccessOut)
async def access(room_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> RoomAccessOut:
    if not get_cached_settings().rooms_can_enter:
        raise HTTPException(status_code=403, detail="rooms_entry_disabled")

    await ensure_room_access_allowed(db, int(ident["id"]))

    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    if str(params.get("entry_closed") or "0") == "1":
        raise HTTPException(status_code=410, detail="room_closed")

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
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:apply:{ident['id']}:{room_id}", limit=10, window_s=1)
@router.post("/{room_id}/apply", response_model=Ok, status_code=202)
async def apply(room_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    if not get_cached_settings().rooms_can_enter:
        raise HTTPException(status_code=403, detail="rooms_entry_disabled")

    await ensure_room_access_allowed(db, int(ident["id"]))

    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    if str(params.get("entry_closed") or "0") == "1":
        raise HTTPException(status_code=410, detail="room_closed")

    if (params.get("privacy") or "open") != "private":
        raise HTTPException(status_code=400, detail="not_private")

    uid = int(ident["id"])
    creator = int(params.get("creator") or 0)
    creator_name = str(params.get("creator_name") or "").strip()
    title = (params.get("title") or "").strip()
    if uid == creator:
        return Ok()

    if await r.sismember(f"room:{room_id}:allow", str(uid)):
        return Ok()

    async with r.pipeline(transaction=True) as p:
        await p.sadd(f"room:{room_id}:pending", str(uid))
        await p.zadd(f"room:{room_id}:requests", {str(uid): int(time())}, nx=True)
        res = await p.execute()

    added_pending = int(res[0] or 0)
    if added_pending == 0:
        return Ok()

    user = await db.get(User, uid)
    if user:
        with suppress(Exception):
            await sio.emit("room_invite",
                           {"room_id": room_id,
                            "room_title": title,
                            "user": {"id": uid, "username": user.username, "avatar_name": user.avatar_name}},
                           room=f"user:{creator}",
                           namespace="/auth")

        details = f"Подача заявки в комнату room_id={room_id} title={title} creator={creator}"
        if creator_name:
            details += f" creator_username={creator_name}"
        await log_action(
            db,
            user_id=uid,
            username=ident["username"],
            action="room_apply",
            details=details,
        )

    return Ok()


@log_route("rooms.list_requests")
@rate_limited(lambda ident, room_id, **_: f"rl:rooms:apps_list:{ident['id']}:{room_id}", limit=10, window_s=1)
@require_room_creator("room_id")
@router.get("/{room_id}/requests", response_model=list[RoomRequestOut])
async def list_requests(room_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)):
    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    if int(params.get("creator") or 0) != int(ident["id"]):
        raise HTTPException(status_code=403, detail="forbidden")

    pending_ids = {int(x) for x in (await r.smembers(f"room:{room_id}:pending") or [])}
    allow_ids = {int(x) for x in (await r.smembers(f"room:{room_id}:allow") or [])}
    ids = pending_ids | allow_ids
    if not ids:
        return []

    raw_order = await r.zrevrange(f"room:{room_id}:requests", 0, -1, withscores=True)
    order_ids: list[int] = []
    request_times: dict[int, datetime] = {}
    seen = set()
    for raw in raw_order or []:
        try:
            uid = int(raw[0])
        except Exception:
            continue
        if uid in ids and uid not in seen:
            order_ids.append(uid)
            seen.add(uid)
        try:
            score = float(raw[1])
            if score > 0:
                request_times[uid] = datetime.fromtimestamp(score, tz=timezone.utc)
        except Exception:
            pass

    missing_ids = sorted(ids - seen)
    if missing_ids:
        async with r.pipeline(transaction=True) as p:
            for idx, uid in enumerate(missing_ids):
                await p.zadd(f"room:{room_id}:requests", {str(uid): -idx}, nx=True)
            await p.execute()
        order_ids.extend(missing_ids)

    rows = await db.execute(select(User).where(User.id.in_(ids)))
    user_map = {int(u.id): u for u in rows.scalars().all()}
    items: list[RoomRequestOut] = []
    for uid in order_ids:
        u = user_map.get(uid)
        if not u:
            continue

        status = "pending" if uid in pending_ids else "approved"
        items.append(RoomRequestOut(
            id=uid,
            username=u.username,
            avatar_name=u.avatar_name,
            role=u.role,
            status=status,
            requested_at=request_times.get(uid),
        ))

    return items


@log_route("rooms.approve")
@rate_limited(lambda ident, room_id, user_id, **_: f"rl:rooms:approve:{ident['id']}:{room_id}", limit=10, window_s=1)
@require_room_creator("room_id")
@router.post("/{room_id}/requests/{user_id}/approve", response_model=Ok)
async def approve(room_id: int, user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    if int(params.get("creator") or 0) != int(ident["id"]):
        raise HTTPException(status_code=403, detail="forbidden")

    async with r.pipeline(transaction=True) as p:
        await p.srem(f"room:{room_id}:pending", str(user_id))
        await p.sadd(f"room:{room_id}:allow", str(user_id))
        await p.zadd(f"room:{room_id}:requests", {str(user_id): int(time())}, nx=True)
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
        await emit_rooms_upsert(room_id)

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

    target_user = await db.get(User, int(user_id))
    target_username = target_user.username if target_user else ""
    details = f"Одобрена заявка в комнату room_id={room_id} title={title_room} target_user={user_id}"
    if target_username:
        details += f" target_username={target_username}"
    await log_action(
        db,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="room_approve",
        details=details,
    )

    return Ok()


@log_route("rooms.deny")
@rate_limited(lambda ident, room_id, user_id, **_: f"rl:rooms:deny:{ident['id']}:{room_id}", limit=10, window_s=1)
@require_room_creator("room_id")
@router.post("/{room_id}/requests/{user_id}/deny", response_model=Ok)
async def deny(room_id: int, user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    params = await get_room_params_or_404(r, room_id)

    if int(params.get("creator") or 0) != int(ident["id"]):
        raise HTTPException(status_code=403, detail="forbidden")

    if (params.get("privacy") or "open") != "private":
        raise HTTPException(status_code=400, detail="not_private")

    raw_gstate = await r.hgetall(f"room:{room_id}:game_state")
    phase = str(raw_gstate.get("phase") or "idle")
    if phase != "idle":
        raise HTTPException(status_code=409, detail="game_in_progress")

    if not await r.sismember(f"room:{room_id}:allow", str(user_id)):
        return Ok()

    async with r.pipeline(transaction=True) as p:
        await p.srem(f"room:{room_id}:allow", str(user_id))
        await p.srem(f"room:{room_id}:pending", str(user_id))
        await p.zrem(f"room:{room_id}:requests", str(user_id))
        res = await p.execute()

    removed = int(res[0] or 0)
    if removed == 0:
        return Ok()

    title_room = (params.get("title") or "").strip()
    is_hidden_room = str(params.get("anonymity") or "visible") == "hidden"
    note = Notif(user_id=int(user_id), title="Доступ к комнате отозван", text=f"Вход в «{title_room}» больше недоступен.")
    db.add(note)
    await db.commit()
    await db.refresh(note)

    with suppress(Exception):
        await sio.emit("notify",
                       {"id": note.id,
                        "title": note.title,
                        "text": note.text,
                        "date": note.created_at.isoformat(),
                        "kind": "info",
                        "room_id": room_id,
                        "ttl_ms": 10000,
                        "read": False},
                       room=f"user:{user_id}",
                       namespace="/auth")
        await sio.emit("room_app_revoked",
                       {"room_id": room_id, "user_id": user_id},
                       room=f"user:{int(ident['id'])}",
                       namespace="/auth")
        await sio.emit("room_app_revoked",
                       {"room_id": room_id, "user_id": user_id},
                       room=f"user:{user_id}",
                       namespace="/auth")
        if is_hidden_room:
            await sio.emit("rooms_remove",
                           {"id": room_id},
                           room=f"user:{user_id}",
                           namespace="/rooms")

    target_user = await db.get(User, int(user_id))
    target_username = target_user.username if target_user else ""
    details = f"Доступ к комнате отозван room_id={room_id} title={title_room} target_user={user_id}"
    if target_username:
        details += f" target_username={target_username}"
    await log_action(
        db,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="room_revoke",
        details=details,
    )

    return Ok()
