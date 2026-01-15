from __future__ import annotations
from typing import cast
import asyncio
from contextlib import suppress
from time import time
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.clients import get_redis
from ...core.db import get_session
from ...models.log import AppLog
from ...models.game import Game
from ...models.room import Room
from ...models.user import User
from ...models.update import SiteUpdate, UpdateRead
from ...realtime.sio import sio
from ...realtime.utils import (
    leave_room_atomic,
    stop_screen_for_user,
    emit_rooms_occupancy_safe,
    record_spectator_leave,
    gc_empty_room,
)
from ...security.decorators import log_route, require_roles_deco
from ...security.parameters import ensure_app_settings, sync_cache_from_row, refresh_app_settings
from ...schemas.common import Ok
from ...schemas.updates import AdminUpdateIn, AdminUpdateOut, AdminUpdatesOut
from ...schemas.admin import (
    AdminSettingsOut,
    AdminSettingsUpdateIn,
    PublicSettingsOut,
    SiteStatsOut,
    PeriodStatsOut,
    AdminLogOut,
    AdminLogsOut,
    AdminLogActionsOut,
    AdminRoomOut,
    AdminRoomGameOut,
    AdminRoomsOut,
    AdminUserOut,
    AdminUsersOut,
    AdminUserRoleIn,
    AdminUserRoleOut,
    AdminGameOut,
    AdminGamesOut,
    AdminGameUserOut,
    AdminGamePlayerOut,
    OnlineUserOut,
)
from ..utils import (
    parse_month_range,
    parse_day_range,
    site_settings_out,
    game_settings_out,
    normalize_pagination,
    build_registrations_series,
    build_registrations_monthly_series,
    calc_total_stream_seconds,
    calc_stream_seconds_in_range,
    fetch_active_rooms_stats,
    fetch_online_users_count,
    fetch_online_user_ids,
    fetch_user_avatar_map,
    fetch_user_name_avatar_maps,
    collect_room_user_ids,
    parse_room_game_params,
    build_room_user_stats,
    sum_room_stream_seconds,
    calc_avg_room_minutes,
    aggregate_user_room_stats,
)

router = APIRouter()

LOG_ACTIONS_KNOWN = {
    "avatar_deleted",
    "avatar_updated",
    "game_end",
    "game_start",
    "login",
    "login_pwa",
    "register",
    "room_apply",
    "room_approve",
    "room_blocks",
    "room_created",
    "room_deleted",
    "room_kick",
    "stream_start",
    "stream_stop",
    "username_updated",
}


@log_route("admin.settings_public")
@router.get("/settings/public", response_model=PublicSettingsOut)
async def public_settings(session: AsyncSession = Depends(get_session)) -> PublicSettingsOut:
    settings = await refresh_app_settings(session)
    return PublicSettingsOut(
        registration_enabled=settings.registration_enabled,
        rooms_can_create=settings.rooms_can_create,
        rooms_can_enter=settings.rooms_can_enter,
        games_can_start=settings.games_can_start,
        streams_can_start=settings.streams_can_start,
        game_min_ready_players=settings.game_min_ready_players,
    )


@log_route("admin.settings_get")
@require_roles_deco("admin")
@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(session: AsyncSession = Depends(get_session)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)

    return AdminSettingsOut(site=site_settings_out(row), game=game_settings_out(row))


@log_route("admin.settings_update")
@require_roles_deco("admin")
@router.patch("/settings", response_model=AdminSettingsOut)
async def update_settings(payload: AdminSettingsUpdateIn, session: AsyncSession = Depends(get_session)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    site_data = data.get("site") or {}
    game_data = data.get("game") or {}
    combined = {**site_data, **game_data}
    for key, value in combined.items():
        setattr(row, key, value)

    if combined:
        await session.commit()
        await session.refresh(row)

    sync_cache_from_row(row)
    if combined:
        with suppress(Exception):
            await get_redis().publish("settings:update", "1")
        try:
            await sio.emit("settings_update", {"ok": True}, namespace="/auth")  
            await sio.emit("settings_update", {"ok": True}, namespace="/rooms")
        except Exception:
            pass

    return AdminSettingsOut(site=site_settings_out(row), game=game_settings_out(row))


@log_route("admin.stats")
@require_roles_deco("admin")
@router.get("/stats", response_model=SiteStatsOut)
async def site_stats(month: str | None = None, session: AsyncSession = Depends(get_session)) -> SiteStatsOut:
    start_dt, end_dt = parse_month_range(month)
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(days=1)
    month_start = start_dt
    month_end = end_dt if end_dt <= now else now
    if month_end < month_start:
        month_end = month_start

    total_users = int(await session.scalar(select(func.count(User.id))) or 0)
    total_rooms = int(await session.scalar(select(func.count(Room.id))) or 0)
    total_games = int(await session.scalar(select(func.count(Game.id))) or 0)
    registrations = await build_registrations_series(session, start_dt, end_dt)
    registrations_monthly = await build_registrations_monthly_series(session)
    total_stream_seconds = await calc_total_stream_seconds(session)
    day_stream_seconds = await calc_stream_seconds_in_range(session, day_start, now)
    month_stream_seconds = await calc_stream_seconds_in_range(session, month_start, month_end)

    r = get_redis()
    active_rooms, active_room_users = await fetch_active_rooms_stats(r)
    online_users = await fetch_online_users_count(r)
    online_ids = await fetch_online_user_ids(r)

    online_users_list: list[OnlineUserOut] = []
    if online_ids:
        name_map, _ = await fetch_user_name_avatar_maps(session, set(online_ids))
        online_ids_sorted = sorted(online_ids, key=lambda uid: (name_map.get(uid) or f"user{uid}").lower())
        online_users_list = [OnlineUserOut(id=uid, username=name_map.get(uid)) for uid in online_ids_sorted]

    day_online_users = int(await session.scalar(select(func.count(User.id)).where(User.last_visit_at >= day_start, User.last_visit_at < now)) or 0)
    month_online_users = int(await session.scalar(select(func.count(User.id)).where(User.last_visit_at >= month_start, User.last_visit_at < month_end)) or 0)
    day_rooms = int(await session.scalar(select(func.count(Room.id)).where(Room.created_at >= day_start, Room.created_at < now)) or 0)
    month_rooms = int(await session.scalar(select(func.count(Room.id)).where(Room.created_at >= month_start, Room.created_at < month_end)) or 0)
    day_games = int(await session.scalar(select(func.count(Game.id)).where(Game.finished_at >= day_start, Game.finished_at < now)) or 0)
    month_games = int(await session.scalar(select(func.count(Game.id)).where(Game.finished_at >= month_start, Game.finished_at < month_end)) or 0)

    total_rooms_avg_minutes = 0
    day_rooms_avg_minutes = 0
    month_rooms_avg_minutes = 0
    if total_rooms > 0:
        rows = await session.execute(select(Room.created_at, Room.deleted_at))
        total_room_rows = [(created_at, deleted_at) for created_at, deleted_at in rows.all()]
        total_rooms_avg_minutes = calc_avg_room_minutes(total_room_rows, now)
    if day_rooms > 0:
        rows = await session.execute(select(Room.created_at, Room.deleted_at).where(Room.created_at >= day_start, Room.created_at < now))
        day_room_rows = [(created_at, deleted_at) for created_at, deleted_at in rows.all()]
        day_rooms_avg_minutes = calc_avg_room_minutes(day_room_rows, now)
    if month_rooms > 0:
        rows = await session.execute(select(Room.created_at, Room.deleted_at).where(Room.created_at >= month_start, Room.created_at < month_end))
        month_room_rows = [(created_at, deleted_at) for created_at, deleted_at in rows.all()]
        month_rooms_avg_minutes = calc_avg_room_minutes(month_room_rows, now)

    return SiteStatsOut(
        total_users=total_users,
        registrations=registrations,
        registrations_monthly=registrations_monthly,
        total_rooms=total_rooms,
        total_rooms_avg_minutes=total_rooms_avg_minutes,
        total_games=total_games,
        total_stream_minutes=total_stream_seconds // 60,
        active_rooms=active_rooms,
        active_room_users=active_room_users,
        online_users=online_users,
        online_users_list=online_users_list,
        last_day=PeriodStatsOut(
            games=day_games,
            online_users=day_online_users,
            rooms=day_rooms,
            rooms_avg_minutes=day_rooms_avg_minutes,
            stream_minutes=day_stream_seconds // 60,
        ),
        last_month=PeriodStatsOut(
            games=month_games,
            online_users=month_online_users,
            rooms=month_rooms,
            rooms_avg_minutes=month_rooms_avg_minutes,
            stream_minutes=month_stream_seconds // 60,
        ),
    )


@log_route("admin.logs.actions")
@require_roles_deco("admin")
@router.get("/logs/actions", response_model=AdminLogActionsOut)
async def log_actions(session: AsyncSession = Depends(get_session)) -> AdminLogActionsOut:
    rows = await session.execute(select(AppLog.action).distinct().order_by(AppLog.action))
    actions = {str(r[0]) for r in rows.all() if r and r[0] is not None}
    actions.update(LOG_ACTIONS_KNOWN)

    return AdminLogActionsOut(actions=sorted(actions))


@log_route("admin.logs.list")
@require_roles_deco("admin")
@router.get("/logs", response_model=AdminLogsOut)
async def logs_list(page: int = 1, limit: int = 20, action: str | None = None, username: str | None = None, day: date | None = None, session: AsyncSession = Depends(get_session)) -> AdminLogsOut:
    limit, page, offset = normalize_pagination(page, limit)

    filters = []
    if action and action != "all":
        filters.append(AppLog.action == action)
    if username:
        filters.append(AppLog.username.ilike(f"%{username}%"))
    if day:
        start_day, end_day = parse_day_range(day)
        filters.append(AppLog.created_at >= start_day)
        filters.append(AppLog.created_at < end_day)

    total = int(await session.scalar(select(func.count(AppLog.id)).where(*filters)) or 0)
    rows = await session.execute(select(AppLog).where(*filters).order_by(AppLog.id.desc()).offset(offset).limit(limit))
    logs = rows.scalars().all()
    user_ids: set[int] = set()
    for row in logs:
        if row.user_id:
            try:
                user_ids.add(int(row.user_id))
            except Exception:
                continue

    avatar_map = await fetch_user_avatar_map(session, user_ids)

    items = [
        AdminLogOut(
            id=row.id,
            user_id=row.user_id,
            username=row.username,
            avatar_name=avatar_map.get(int(row.user_id)) if row.user_id else None,
            action=row.action,
            details=row.details,
            created_at=row.created_at,
        )
        for row in logs
    ]

    return AdminLogsOut(total=total, items=items)


@log_route("admin.rooms.list")
@require_roles_deco("admin")
@router.get("/rooms", response_model=AdminRoomsOut)
async def rooms_list(page: int = 1, limit: int = 20, username: str | None = None, stream_only: bool | None = None, session: AsyncSession = Depends(get_session)) -> AdminRoomsOut:
    limit, page, offset = normalize_pagination(page, limit)

    query = select(Room)
    filters = []
    if username:
        rows = await session.execute(select(User.id).where(User.username.ilike(f"%{username}%")))
        ids = [int(x[0]) for x in rows.all()]
        if not ids:
            return AdminRoomsOut(total=0, items=[])

        id_strs = [str(i) for i in ids]
        user_filters = [Room.creator.in_(ids)]
        user_filters += [Room.visitors.has_key(i) for i in id_strs]
        user_filters += [Room.spectators_time.has_key(i) for i in id_strs]
        filters.append(or_(*user_filters))

    if stream_only:
        filters.append(Room.screen_time != {})

    if filters:
        query = query.where(*filters)

    total = int(await session.scalar(select(func.count(Room.id)).where(*filters)) or 0)
    rows = await session.execute(query.order_by(Room.created_at.desc(), Room.id.desc()).offset(offset).limit(limit))
    rooms = rows.scalars().all()
    user_ids = collect_room_user_ids(rooms)
    name_map, avatar_map = await fetch_user_name_avatar_maps(session, user_ids)
    room_ids = [int(room.id) for room in rooms]
    games_map: dict[int, list[tuple[str, datetime, datetime]]] = {}
    if room_ids:
        game_rows = await session.execute(
            select(Game.room_id, Game.result, Game.started_at, Game.finished_at, Game.id)
            .where(Game.room_id.in_(room_ids))
            .order_by(Game.room_id.asc(), Game.started_at.asc(), Game.id.asc())
        )
        for room_id, result, started_at, finished_at, _game_id in game_rows.all():
            try:
                rid_int = int(room_id)
            except Exception:
                continue
            games_map.setdefault(rid_int, []).append((str(result), started_at, finished_at))

    items: list[AdminRoomOut] = []
    for room in rooms:
        visitors_count = len(room.visitors or {})
        spectators_count = len(room.spectators_time or {})
        stream_seconds = sum_room_stream_seconds(room.screen_time)
        game_params = parse_room_game_params(room.game)
        visitors_items = build_room_user_stats(room.visitors, name_map)
        spectators_items = build_room_user_stats(room.spectators_time, name_map)
        stream_items = build_room_user_stats(room.screen_time, name_map)
        room_games = games_map.get(int(room.id), [])
        game_items: list[AdminRoomGameOut] = []
        for index, (result, started_at, finished_at) in enumerate(room_games):
            try:
                duration_sec = int((finished_at - started_at).total_seconds())
            except Exception:
                duration_sec = 0
            duration_min = max(0, duration_sec // 60)
            game_items.append(AdminRoomGameOut(number=index + 1, result=result, minutes=duration_min))

        items.append(
            AdminRoomOut(
                id=room.id,
                creator=int(room.creator),
                creator_name=room.creator_name,
                creator_avatar_name=avatar_map.get(int(room.creator)),
                title=room.title,
                user_limit=room.user_limit,
                privacy=room.privacy,
                created_at=room.created_at,
                deleted_at=room.deleted_at,
                game_mode=game_params["mode"],
                game_format=game_params["format"],
                spectators_limit=game_params["spectators_limit"],
                break_at_zero=game_params["break_at_zero"],
                lift_at_zero=game_params["lift_at_zero"],
                lift_3x=game_params["lift_3x"],
                visitors_count=visitors_count,
                visitors=visitors_items,
                spectators_count=spectators_count,
                spectators=spectators_items,
                games=game_items,
                stream_minutes=stream_seconds // 60,
                streamers=stream_items,
                has_stream=stream_seconds > 0,
            )
        )

    return AdminRoomsOut(total=total, items=items)


@log_route("admin.rooms.kick_all")
@require_roles_deco("admin")
@router.post("/rooms/kick", response_model=Ok)
async def rooms_kick_all() -> Ok:
    r = get_redis()
    try:
        room_ids_raw = await r.zrange("rooms:index", 0, -1)
    except Exception:
        room_ids_raw = []

    for raw_id in room_ids_raw:
        try:
            rid = int(raw_id)
        except Exception:
            continue

        try:
            members_raw = await r.smembers(f"room:{rid}:members")
        except Exception:
            members_raw = set()
        try:
            spectators_raw = await r.smembers(f"room:{rid}:spectators")
        except Exception:
            spectators_raw = set()

        member_ids: set[int] = set()
        for v in members_raw or []:
            try:
                member_ids.add(int(v))
            except Exception:
                continue

        spectator_ids: set[int] = set()
        for v in spectators_raw or []:
            try:
                spectator_ids.add(int(v))
            except Exception:
                continue

        gc_seq_on_empty: int | None = None
        for uid in member_ids:
            await sio.emit("force_leave",
                           {"room_id": rid, "reason": "admin_kick_all"},
                           room=f"user:{uid}",
                           namespace="/room")
            try:
                await stop_screen_for_user(r, rid, uid)
                occ, gc_seq, pos_updates = await leave_room_atomic(r, rid, uid)
                if occ == 0:
                    gc_seq_on_empty = gc_seq
            except Exception:
                continue

            try:
                await r.srem(f"room:{rid}:ready", str(uid))
            except Exception:
                pass
            try:
                await r.delete(f"room:{rid}:user:{uid}:epoch")
            except Exception:
                pass

            await sio.emit("member_left",
                           {"user_id": uid},
                           room=f"room:{rid}",
                           namespace="/room")
            if pos_updates:
                await sio.emit("positions",
                               {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                               room=f"room:{rid}",
                               namespace="/room")
            await emit_rooms_occupancy_safe(r, rid, occ)

        for uid in spectator_ids - member_ids:
            await sio.emit("force_leave",
                           {"room_id": rid, "reason": "admin_kick_all"},
                           room=f"user:{uid}",
                           namespace="/room")
            try:
                await record_spectator_leave(r, rid, uid, int(time()))
            except Exception:
                pass

        should_gc = gc_seq_on_empty is not None
        if not should_gc:
            try:
                occ = int(await r.scard(f"room:{rid}:members") or 0)
            except Exception:
                occ = -1
            should_gc = occ == 0
        if should_gc:
            rid_snapshot = rid
            gc_seq_snapshot = gc_seq_on_empty

            async def _gc():
                with suppress(Exception):
                    removed = await gc_empty_room(rid_snapshot, expected_seq=gc_seq_snapshot)
                    if removed:
                        await sio.emit("rooms_remove",
                                       {"id": rid_snapshot},
                                       namespace="/rooms")

            asyncio.create_task(_gc())

    return Ok()


@log_route("admin.games.list")
@require_roles_deco("admin")
@router.get("/games", response_model=AdminGamesOut)
async def games_list(page: int = 1, limit: int = 20, username: str | None = None, day: date | None = None, session: AsyncSession = Depends(get_session)) -> AdminGamesOut:
    limit, page, offset = normalize_pagination(page, limit)
    filters = []
    if day:
        start_dt, end_dt = parse_day_range(day)
        filters.append(Game.started_at >= start_dt)
        filters.append(Game.started_at < end_dt)

    if username:
        rows = await session.execute(select(User.id).where(User.username.ilike(f"%{username}%")))
        ids = [int(x[0]) for x in rows.all()]
        if not ids:
            return AdminGamesOut(total=0, items=[])

        role_filters = [Game.roles.has_key(str(uid)) for uid in ids]
        filters.append(or_(Game.head_id.in_(ids), *role_filters))

    total = int(await session.scalar(select(func.count(Game.id)).where(*filters)) or 0)
    rows = await session.execute(select(Game).where(*filters).order_by(Game.started_at.desc(), Game.id.desc()).offset(offset).limit(limit))
    games = rows.scalars().all()

    user_ids: set[int] = set()
    for game in games:
        try:
            user_ids.add(int(game.room_owner_id))
        except Exception:
            pass
        if game.head_id:
            try:
                user_ids.add(int(game.head_id))
            except Exception:
                pass
        seats_map = game.seats or {}
        if isinstance(seats_map, dict):
            for uid in seats_map.keys():
                try:
                    user_ids.add(int(uid))
                except Exception:
                    continue

    user_map: dict[int, tuple[str | None, str | None]] = {}
    if user_ids:
        rows = await session.execute(select(User.id, User.username, User.avatar_name).where(User.id.in_(user_ids)))
        for uid, uname, ava in rows.all():
            user_map[int(uid)] = (uname, ava)

    items: list[AdminGameOut] = []
    for game in games:
        owner_id = int(game.room_owner_id)
        owner_info = user_map.get(owner_id, (None, None))
        owner = AdminGameUserOut(id=owner_id, username=owner_info[0], avatar_name=owner_info[1])

        head = None
        if game.head_id:
            head_id = int(game.head_id)
            head_info = user_map.get(head_id, (None, None))
            head = AdminGameUserOut(id=head_id, username=head_info[0], avatar_name=head_info[1])

        roles_map = game.roles or {}
        seats_map = game.seats or {}
        points_map = game.points or {}
        mmr_map = game.mmr or {}

        players: list[AdminGamePlayerOut] = []
        if isinstance(seats_map, dict):
            for uid_raw, seat_raw in seats_map.items():
                try:
                    uid = int(uid_raw)
                    seat = int(seat_raw or 0)
                except Exception:
                    continue
                if seat <= 0:
                    continue

                user_info = user_map.get(uid, (None, None))
                role = str(roles_map.get(str(uid)) or "")
                points = int(points_map.get(str(uid)) or 0)
                mmr = int(mmr_map.get(str(uid)) or 0)
                players.append(AdminGamePlayerOut(
                    seat=seat,
                    id=uid,
                    username=user_info[0],
                    avatar_name=user_info[1],
                    role=role,
                    points=points,
                    mmr=mmr,
                ))
        players.sort(key=lambda p: p.seat)

        try:
            duration_seconds = int((game.finished_at - game.started_at).total_seconds())
        except Exception:
            duration_seconds = 0
        duration_seconds = max(0, duration_seconds)

        items.append(AdminGameOut(
            id=int(game.id),
            room_id=int(game.room_id),
            owner=owner,
            head=head,
            result=str(game.result),
            black_alive_at_finish=int(game.black_alive_at_finish),
            started_at=game.started_at,
            finished_at=game.finished_at,
            duration_seconds=duration_seconds,
            players=players,
            actions=list(game.actions or []),
        ))

    return AdminGamesOut(total=total, items=items)


@log_route("admin.users.list")
@require_roles_deco("admin")
@router.get("/users", response_model=AdminUsersOut)
async def users_list(page: int = 1, limit: int = 20, username: str | None = None, session: AsyncSession = Depends(get_session),) -> AdminUsersOut:
    limit, page, offset = normalize_pagination(page, limit)

    filters = []
    if username:
        filters.append(User.username.ilike(f"%{username}%"))

    total = int(await session.scalar(select(func.count(User.id)).where(*filters)) or 0)
    rows = await session.execute(select(User).where(*filters).order_by(User.registered_at.desc(), User.id.desc()).offset(offset).limit(limit))
    users = rows.scalars().all()
    ids = [int(u.id) for u in users]
    rooms_created, room_lifetime_seconds, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = await aggregate_user_room_stats(session, ids)

    items: list[AdminUserOut] = []
    for u in users:
        uid = int(u.id)
        created = rooms_created.get(uid, 0)
        lifetime_seconds = room_lifetime_seconds.get(uid, 0)
        rooms_avg_minutes = (lifetime_seconds // created) // 60 if created > 0 else 0
        items.append(AdminUserOut(
            id=uid,
            username=u.username,
            avatar_name=u.avatar_name,
            role=u.role,
            registered_at=u.registered_at,
            last_login_at=u.last_login_at,
            last_visit_at=u.last_visit_at,
            rooms_created=created,
            rooms_avg_minutes=rooms_avg_minutes,
            room_minutes=room_seconds.get(uid, 0) // 60,
            stream_minutes=stream_seconds.get(uid, 0) // 60,
            games_played=games_played.get(uid, 0),
            games_hosted=games_hosted.get(uid, 0),
            spectator_minutes=spectator_seconds.get(uid, 0) // 60,
        ))

    return AdminUsersOut(total=total, items=items)


@log_route("admin.users.role")
@require_roles_deco("admin")
@router.patch("/users/{user_id}/role", response_model=AdminUserRoleOut)
async def update_user_role(user_id: int, payload: AdminUserRoleIn, session: AsyncSession = Depends(get_session)) -> AdminUserRoleOut:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    user.role = payload.role
    await session.commit()
    await session.refresh(user)

    return AdminUserRoleOut(id=cast(int, user.id), role=user.role)


@log_route("admin.updates.list")
@require_roles_deco("admin")
@router.get("/updates", response_model=AdminUpdatesOut)
async def updates_list(session: AsyncSession = Depends(get_session)) -> AdminUpdatesOut:
    rows = await session.execute(select(SiteUpdate).order_by(SiteUpdate.update_date.desc(), SiteUpdate.id.desc()))
    items = [
        AdminUpdateOut(
            id=row.id,
            version=row.version,
            date=row.update_date,
            description=row.description,
        )
        for row in rows.scalars().all()
    ]

    return AdminUpdatesOut(items=items)


@log_route("admin.updates.create")
@require_roles_deco("admin")
@router.post("/updates", response_model=AdminUpdateOut)
async def updates_create(payload: AdminUpdateIn, session: AsyncSession = Depends(get_session)) -> AdminUpdateOut:
    row = SiteUpdate(
        version=payload.version,
        update_date=payload.date,
        description=payload.description,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    try:
        await sio.emit("site_update", {"id": row.id}, namespace="/auth")
    except Exception:
        pass

    return AdminUpdateOut(id=row.id, version=row.version, date=row.update_date, description=row.description)


@log_route("admin.updates.update")
@require_roles_deco("admin")
@router.patch("/updates/{update_id}", response_model=AdminUpdateOut)
async def updates_update(update_id: int, payload: AdminUpdateIn, session: AsyncSession = Depends(get_session)) -> AdminUpdateOut:
    row = await session.get(SiteUpdate, int(update_id))
    if not row:
        raise HTTPException(status_code=404, detail="update_not_found")

    row.version = payload.version
    row.update_date = payload.date
    row.description = payload.description
    await session.commit()
    await session.refresh(row)

    return AdminUpdateOut(id=row.id, version=row.version, date=row.update_date, description=row.description)


@log_route("admin.updates.delete")
@require_roles_deco("admin")
@router.delete("/updates/{update_id}", response_model=Ok)
async def updates_delete(update_id: int, session: AsyncSession = Depends(get_session)) -> Ok:
    row = await session.get(SiteUpdate, int(update_id))
    if not row:
        raise HTTPException(status_code=404, detail="update_not_found")

    await session.execute(delete(UpdateRead).where(UpdateRead.update_id == int(update_id)))
    await session.delete(row)
    await session.commit()
    return Ok()
