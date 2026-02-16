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
from ...models.notif import Notif
from ...models.sanction import UserSanction
from ...models.user import User
from ...models.update import SiteUpdate, UpdateRead
from ...core.logging import log_action
from ...realtime.sio import sio
from ...realtime.utils import (
    leave_room_atomic,
    stop_screen_for_user,
    emit_rooms_occupancy_safe,
    record_spectator_leave,
)
from ...security.decorators import log_route, require_roles_deco
from ...security.auth_tokens import get_identity
from ...security.passwords import hash_password
from ...security.parameters import ensure_app_settings, sync_cache_from_row, refresh_app_settings, get_cached_settings
from ...schemas.common import Ok, Identity
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
    AdminSanctionTimedIn,
    AdminSanctionBanIn,
    OnlineUserOut,
)
from ..utils import (
    SANCTION_TIMEOUT,
    SANCTION_BAN,
    SANCTION_SUSPEND,
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
    fetch_online_user_ids,
    fetch_effective_online_user_ids,
    fetch_user_avatar_map,
    fetch_user_name_avatar_maps,
    collect_room_user_ids,
    parse_room_game_params,
    build_room_user_stats,
    sum_room_stream_seconds,
    fetch_live_room_stats,
    aggregate_user_room_stats,
    fetch_friends_count_for_users,
    fetch_sanction_counts_for_users,
    normalize_users_sort,
    user_sort_metric,
    compute_duration_seconds,
    gc_empty_room_and_emit,
    fetch_active_sanction,
    fetch_sanctions_for_users,
    is_sanction_active,
    build_admin_sanction_out,
    format_duration_parts,
    emit_sanctions_update,
    refresh_rooms_after,
    set_user_deleted,
    force_logout_user,
    is_protected_admin,
    ensure_admin_target_allowed,
    emit_rooms_upsert,
    get_room_params_or_404,
)

router = APIRouter()

LOG_ACTIONS_KNOWN = {
    "avatar_deleted",
    "avatar_updated",
    "account_deleted",
    "game_end",
    "game_start",
    "login",
    "login_pwa",
    "register",
    "room_apply",
    "room_approve",
    "room_revoke",
    "room_blocks",
    "room_created",
    "room_deleted",
    "room_kick",
    "stream_start",
    "stream_stop",
    "username_updated",
    "sanction_timeout_add",
    "sanction_timeout_remove",
    "sanction_ban_add",
    "sanction_ban_remove",
    "sanction_suspend_add",
    "sanction_suspend_remove",
    "admin_telegram_unverify",
    "admin_password_clear",
    "friend_request_sent",
    "friend_request_accepted",
    "friend_request_declined",
    "friend_removed",
    "friend_room_invite",
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
        verification_restrictions=settings.verification_restrictions,
        game_min_ready_players=settings.game_min_ready_players,
        winks_limit=settings.winks_limit,
        knocks_limit=settings.knocks_limit,
        wink_spot_chance_percent=settings.wink_spot_chance_percent,
        season_start_game_number=settings.season_start_game_number,
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
    unverified_users = int(await session.scalar(select(func.count(User.id)).where(User.telegram_id.is_(None))) or 0)
    no_password_users = int(await session.scalar(select(func.count(User.id)).where(User.password_hash.is_(None))) or 0)
    deleted_users = int(await session.scalar(select(func.count(User.id)).where(User.deleted_at.is_not(None))) or 0)
    tg_invites_disabled_users = int(await session.scalar(select(func.count(User.id)).where(User.tg_invites_enabled.is_(False))) or 0)
    total_rooms = int(await session.scalar(select(func.count(Room.id))) or 0)
    total_games = int(await session.scalar(select(func.count(Game.id))) or 0)
    registrations = await build_registrations_series(session, start_dt, end_dt)
    registrations_monthly = await build_registrations_monthly_series(session)
    total_stream_seconds = await calc_total_stream_seconds(session)
    day_stream_seconds = await calc_stream_seconds_in_range(session, day_start, now)
    month_stream_seconds = await calc_stream_seconds_in_range(session, month_start, month_end)

    r = get_redis()
    active_rooms, active_room_users = await fetch_active_rooms_stats(r)
    base_online_ids = set(await fetch_online_user_ids(r))
    room_presence_ids: set[int] = set()
    try:
        raw_room_ids = await r.zrange("rooms:index", 0, -1)
        room_ids = [int(x) for x in (raw_room_ids or []) if int(x) > 0]
    except Exception:
        room_ids = []

    if room_ids:
        try:
            async with r.pipeline() as p:
                for rid in room_ids:
                    await p.smembers(f"room:{rid}:members")
                    await p.smembers(f"room:{rid}:spectators")
                room_sets = await p.execute()
            for raw_set in room_sets or []:
                for raw_uid in raw_set or []:
                    try:
                        uid = int(raw_uid)
                    except Exception:
                        continue
                    if uid > 0:
                        room_presence_ids.add(uid)
        except Exception:
            room_presence_ids = set()

    candidate_online_ids = base_online_ids | room_presence_ids
    online_ids = await fetch_effective_online_user_ids(r, candidate_online_ids, base_online_ids=base_online_ids)
    online_users = len(online_ids)

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

    return SiteStatsOut(
        total_users=total_users,
        unverified_users=unverified_users,
        no_password_users=no_password_users,
        deleted_users=deleted_users,
        tg_invites_disabled_users=tg_invites_disabled_users,
        registrations=registrations,
        registrations_monthly=registrations_monthly,
        total_rooms=total_rooms,
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
            stream_minutes=day_stream_seconds // 60,
        ),
        last_month=PeriodStatsOut(
            games=month_games,
            online_users=month_online_users,
            rooms=month_rooms,
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
        needle = username.lower()
        filters.append(or_(func.lower(AppLog.username).contains(needle, autoescape=True),
                           func.lower(AppLog.details).contains(needle, autoescape=True)))
    if day:
        start_day, end_day = parse_day_range(day)
        filters.append(AppLog.created_at >= start_day)
        filters.append(AppLog.created_at < end_day)

    total = int(await session.scalar(select(func.count(AppLog.id)).where(*filters)) or 0)
    rows = await session.execute(select(AppLog).where(*filters).order_by(AppLog.id.desc()).offset(offset).limit(limit))
    logs = rows.scalars().all()
    user_ids: set[int] = set()
    for row in logs:
        if row.user_id is not None:
            user_ids.add(cast(int, row.user_id))

    avatar_map = await fetch_user_avatar_map(session, user_ids)

    items: list[AdminLogOut] = []
    for row in logs:
        uid = cast(int, row.user_id) if row.user_id is not None else None
        items.append(
            AdminLogOut(
                id=row.id,
                user_id=row.user_id,
                username=row.username,
                avatar_name=avatar_map.get(uid) if uid is not None else None,
                action=row.action,
                details=row.details,
                created_at=row.created_at,
            )
        )

    return AdminLogsOut(total=total, items=items)


@log_route("admin.rooms.list")
@require_roles_deco("admin")
@router.get("/rooms", response_model=AdminRoomsOut)
async def rooms_list(page: int = 1, limit: int = 20, username: str | None = None, stream_only: bool | None = None, session: AsyncSession = Depends(get_session)) -> AdminRoomsOut:
    limit, page, offset = normalize_pagination(page, limit)

    query = select(Room)
    filters = []
    if username:
        needle = username.lower()
        rows = await session.execute(select(User.id).where(func.lower(User.username).contains(needle, autoescape=True)))
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
    active_ids = [int(room.id) for room in rooms if room.deleted_at is None]
    live_stats = await fetch_live_room_stats(get_redis(), active_ids)

    user_ids = collect_room_user_ids(rooms)
    for stats in live_stats.values():
        for k in stats["visitors"].keys():
            try:
                user_ids.add(int(k))
            except Exception:
                continue
        for k in stats["spectators"].keys():
            try:
                user_ids.add(int(k))
            except Exception:
                continue
        for k in stats["streams"].keys():
            try:
                user_ids.add(int(k))
            except Exception:
                continue

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
        stats = live_stats.get(int(room.id)) if room.deleted_at is None else None
        visitors_map = stats["visitors"] if stats else (room.visitors or {})
        spectators_map = stats["spectators"] if stats else (room.spectators_time or {})
        stream_map = stats["streams"] if stats else (room.screen_time or {})
        visitors_count = stats["visitors_count"] if stats else len(room.visitors or {})
        spectators_count = stats["spectators_count"] if stats else len(room.spectators_time or {})
        stream_seconds = stats["stream_seconds"] if stats else sum_room_stream_seconds(room.screen_time)
        game_params = parse_room_game_params(room.game)
        visitors_items = build_room_user_stats(visitors_map, name_map)
        spectators_items = build_room_user_stats(spectators_map, name_map)
        stream_items = build_room_user_stats(stream_map, name_map)
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
                nominate_mode=game_params["nominate_mode"],
                break_at_zero=game_params["break_at_zero"],
                lift_at_zero=game_params["lift_at_zero"],
                lift_3x=game_params["lift_3x"],
                wink_knock=game_params["wink_knock"],
                farewell_wills=game_params["farewell_wills"],
                music=game_params["music"],
                visitors_count=visitors_count,
                visitors=visitors_items,
                spectators_count=spectators_count,
                spectators=spectators_items,
                games=game_items,
                stream_minutes=stream_seconds // 60,
                streamers=stream_items,
                has_stream=stats["has_stream"] if stats else (stream_seconds > 0),
            )
        )

    return AdminRoomsOut(total=total, items=items)


@log_route("admin.rooms.close")
@require_roles_deco("admin")
@router.post("/rooms/{room_id}/close", response_model=Ok)
async def room_close(room_id: int) -> Ok:
    r = get_redis()
    await get_room_params_or_404(r, room_id)

    phase = str(await r.hget(f"room:{room_id}:game_state", "phase") or "idle")
    if phase != "idle":
        raise HTTPException(status_code=409, detail="room_in_game")

    await r.hset(f"room:{room_id}:params", mapping={"entry_closed": "1"})
    await emit_rooms_upsert(room_id)

    try:
        members_raw = await r.smembers(f"room:{room_id}:members")
    except Exception:
        members_raw = set()
    try:
        spectators_raw = await r.smembers(f"room:{room_id}:spectators")
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
                       {"room_id": room_id, "reason": "room_deleted"},
                       room=f"user:{uid}",
                       namespace="/room")
        try:
            await stop_screen_for_user(r, room_id, uid)
            occ, gc_seq, pos_updates = await leave_room_atomic(r, room_id, uid)
            if occ == 0:
                gc_seq_on_empty = gc_seq
        except Exception:
            continue

        try:
            await r.srem(f"room:{room_id}:ready", str(uid))
        except Exception:
            pass
        try:
            await r.delete(f"room:{room_id}:user:{uid}:epoch")
        except Exception:
            pass

        await sio.emit("member_left",
                       {"user_id": uid},
                       room=f"room:{room_id}",
                       namespace="/room")
        if pos_updates:
            await sio.emit("positions",
                           {"updates": [{"user_id": u, "position": p} for u, p in pos_updates]},
                           room=f"room:{room_id}",
                           namespace="/room")
        await emit_rooms_occupancy_safe(r, room_id, occ)

    for uid in spectator_ids - member_ids:
        await sio.emit("force_leave",
                       {"room_id": room_id, "reason": "room_deleted"},
                       room=f"user:{uid}",
                       namespace="/room")
        try:
            await record_spectator_leave(r, room_id, uid, int(time()))
        except Exception:
            pass

    should_gc = gc_seq_on_empty is not None
    if not should_gc:
        try:
            occ = int(await r.scard(f"room:{room_id}:members") or 0)
        except Exception:
            occ = -1
        should_gc = occ == 0
    if should_gc:
        rid_snapshot = room_id
        gc_seq_snapshot = gc_seq_on_empty
        asyncio.create_task(gc_empty_room_and_emit(rid_snapshot, expected_seq=gc_seq_snapshot))

    return Ok()


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
            await r.hset(f"room:{rid}:params", mapping={"entry_closed": "1"})
            await emit_rooms_upsert(rid)
        except Exception:
            pass

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
            asyncio.create_task(gc_empty_room_and_emit(rid_snapshot, expected_seq=gc_seq_snapshot))

    delay_s = max(0, int(get_cached_settings().rooms_empty_ttl_seconds))

    asyncio.create_task(refresh_rooms_after(delay_s + 1, "admin_kick_all"))

    return Ok()


@log_route("admin.users.list")
@require_roles_deco("admin")
@router.get("/users", response_model=AdminUsersOut)
async def users_list(page: int = 1, limit: int = 20, username: str | None = None, sort_by: str | None = None, session: AsyncSession = Depends(get_session)) -> AdminUsersOut:
    limit, page, offset = normalize_pagination(page, limit)
    sort_key = normalize_users_sort(sort_by)

    filters = []
    if username:
        needle = username.lower()
        filters.append(func.lower(User.username).contains(needle, autoescape=True))

    users: list[User]
    friends_count: dict[int, int]
    rooms_created: dict[int, int]
    room_seconds: dict[int, int]
    stream_seconds: dict[int, int]
    spectator_seconds: dict[int, int]
    games_played: dict[int, int]
    games_hosted: dict[int, int]

    if sort_key == "registered_at":
        total = int(await session.scalar(select(func.count(User.id)).where(*filters)) or 0)
        rows = await session.execute(select(User) .where(*filters) .order_by(User.registered_at.desc(), User.id.desc()) .offset(offset) .limit(limit))
        users = rows.scalars().all()
        ids = [int(u.id) for u in users]
        friends_count = await fetch_friends_count_for_users(session, ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = await aggregate_user_room_stats(session, ids)
    else:
        rows = await session.execute(select(User).where(*filters))
        all_users = rows.scalars().all()
        total = len(all_users)
        all_ids = [int(u.id) for u in all_users]
        friends_count = await fetch_friends_count_for_users(session, all_ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = await aggregate_user_room_stats(session, all_ids)
        sanction_counts = await fetch_sanction_counts_for_users(session, all_ids)

        users_sorted = sorted(
            all_users,
            key=lambda u: (
                user_sort_metric(
                    sort_by=sort_key,
                    uid=int(u.id),
                    friends_count=friends_count,
                    rooms_created=rooms_created,
                    room_seconds=room_seconds,
                    stream_seconds=stream_seconds,
                    games_played=games_played,
                    games_hosted=games_hosted,
                    spectator_seconds=spectator_seconds,
                    sanction_counts=sanction_counts,
                ),
                u.registered_at,
                int(u.id),
            ),
            reverse=True,
        )
        users = users_sorted[offset:offset + limit]

    ids = [int(u.id) for u in users]
    sanctions_map = await fetch_sanctions_for_users(session, ids)
    now = datetime.now(timezone.utc)
    items: list[AdminUserOut] = []
    for u in users:
        uid = int(u.id)
        created = rooms_created.get(uid, 0)
        user_sanctions = sanctions_map.get(uid, [])
        timeouts_raw = [s for s in user_sanctions if s.kind == SANCTION_TIMEOUT]
        bans_raw = [s for s in user_sanctions if s.kind == SANCTION_BAN]
        suspends_raw = [s for s in user_sanctions if s.kind == SANCTION_SUSPEND]
        active_timeout = next((s for s in timeouts_raw if is_sanction_active(s, now)), None)
        active_ban = next((s for s in bans_raw if is_sanction_active(s, now)), None)
        active_suspend = next((s for s in suspends_raw if is_sanction_active(s, now)), None)
        items.append(AdminUserOut(
            id=uid,
            username=u.username,
            avatar_name=u.avatar_name,
            role=u.role,
            telegram_verified=bool(u.telegram_id),
            has_password=bool(u.password_hash),
            protected_user=is_protected_admin(uid),
            registered_at=u.registered_at,
            last_login_at=u.last_login_at,
            last_visit_at=u.last_visit_at,
            deleted_at=u.deleted_at,
            friends_count=friends_count.get(uid, 0),
            rooms_created=created,
            room_minutes=room_seconds.get(uid, 0) // 60,
            stream_minutes=stream_seconds.get(uid, 0) // 60,
            games_played=games_played.get(uid, 0),
            games_hosted=games_hosted.get(uid, 0),
            spectator_minutes=spectator_seconds.get(uid, 0) // 60,
            timeout_active=active_timeout is not None,
            timeout_until=active_timeout.expires_at if active_timeout else None,
            ban_active=active_ban is not None,
            suspend_active=active_suspend is not None,
            suspend_until=active_suspend.expires_at if active_suspend else None,
            timeouts_count=len(timeouts_raw),
            bans_count=len(bans_raw),
            suspends_count=len(suspends_raw),
            timeouts=[build_admin_sanction_out(s) for s in timeouts_raw],
            bans=[build_admin_sanction_out(s) for s in bans_raw],
            suspends=[build_admin_sanction_out(s) for s in suspends_raw],
        ))

    return AdminUsersOut(total=total, items=items)


@log_route("admin.users.role")
@require_roles_deco("admin")
@router.patch("/users/{user_id}/role", response_model=AdminUserRoleOut)
async def update_user_role(user_id: int, payload: AdminUserRoleIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminUserRoleOut:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    prev_role = user.role
    user.role = payload.role
    await session.commit()
    await session.refresh(user)

    uid = cast(int, user.id)
    if prev_role != user.role:
        action = "admin_role_grant" if user.role == "admin" else "admin_role_revoke"
        details = f"Роль user_id={uid}"
        if user.username:
            details += f" username={user.username}"
        details += f" from={prev_role} to={user.role}"

        await log_action(
            session,
            user_id=int(ident["id"]),
            username=ident["username"],
            action=action,
            details=details,
        )

        if user.role == "admin":
            note = Notif(
                user_id=uid,
                title="Администратор",
                text="Вам выданы права администратора.",
            )
            session.add(note)
            await session.commit()
            await session.refresh(note)
            with suppress(Exception):
                await sio.emit(
                    "notify",
                    {
                        "id": note.id,
                        "title": note.title,
                        "text": note.text,
                        "date": note.created_at.isoformat(),
                        "kind": "admin_action",
                        "ttl_ms": 15000,
                        "read": False,
                    },
                    room=f"user:{uid}",
                    namespace="/auth",
                )

    return AdminUserRoleOut(id=uid, role=user.role)


@log_route("admin.users.account_delete")
@require_roles_deco("admin")
@router.post("/users/{user_id}/delete", response_model=Ok)
async def delete_user_account(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    target = await session.get(User, int(user_id))
    if not target:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(target)
    user = await set_user_deleted(session, int(user_id), deleted=True)
    uid = cast(int, user.id)
    details = f"Удаление аккаунта user_id={uid}"
    if user.username:
        details += f" username={user.username}"

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_account_delete",
        details=details,
    )

    note = Notif(
        user_id=uid,
        title="Аккаунт удален",
        text="Ваш аккаунт был удален администратором.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)
    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "admin_action",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
    await force_logout_user(int(user_id))
    return Ok()


@log_route("admin.users.account_restore")
@require_roles_deco("admin")
@router.post("/users/{user_id}/restore", response_model=Ok)
async def restore_user_account(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    target = await session.get(User, int(user_id))
    if not target:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(target)
    user = await set_user_deleted(session, int(user_id), deleted=False)
    details = f"Восстановление аккаунта user_id={user.id}"
    if user.username:
        details += f" username={user.username}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_account_restore",
        details=details,
    )
    return Ok()


@log_route("admin.users.unverify")
@require_roles_deco("admin")
@router.post("/users/{user_id}/unverify", response_model=Ok)
async def unverify_user(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    prev_tg = user.telegram_id
    if prev_tg is None:
        return Ok()

    user.telegram_id = None
    note = Notif(
        user_id=uid,
        title="Верификация снята",
        text="Администратор снял верификацию с вашего аккаунта.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    details = f"Снятие верификации user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" tg_id={prev_tg}"

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_telegram_unverify",
        details=details,
    )

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "admin_action",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
    return Ok()


@log_route("admin.users.password_clear")
@require_roles_deco("admin")
@router.post("/users/{user_id}/password_clear", response_model=Ok)
async def clear_user_password(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    had_password = bool(user.password_hash)
    user.password_hash = hash_password("12345678")
    user.password_temp = True
    note = Notif(
        user_id=uid,
        title="Пароль сброшен",
        text="Администратор сбросил пароль Вашего аккаунта.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    details = f"Сброс пароля user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" had_password={int(had_password)}"

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_password_clear",
        details=details,
    )

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "admin_action",
                "ttl_ms": 15000,
                "read": False,
                "toast_text": "Ваш пароль сброшен администратором",
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
    return Ok()


@log_route("admin.users.timeout_add")
@require_roles_deco("admin")
@router.post("/users/{user_id}/timeout", response_model=Ok)
async def apply_user_timeout(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_TIMEOUT)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    months = int(payload.months or 0)
    days = int(payload.days or 0)
    hours = int(payload.hours or 0)
    minutes = int(payload.minutes or 0)
    duration_seconds = compute_duration_seconds(months, days, hours, minutes)
    if duration_seconds <= 0:
        raise HTTPException(status_code=422, detail="duration_required")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=duration_seconds)
    reason = payload.reason.strip()
    duration_label = format_duration_parts(months, days, hours, minutes)

    sanction = UserSanction(
        user_id=uid,
        kind=SANCTION_TIMEOUT,
        reason=reason,
        issued_at=now,
        issued_by_id=int(ident["id"]),
        issued_by_name=ident["username"],
        duration_seconds=duration_seconds,
        expires_at=expires_at,
    )
    note = Notif(
        user_id=uid,
        title="Таймаут",
        text=f"Вам выдан таймаут на {duration_label}. Причина: {reason}.",
    )
    session.add(sanction)
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)
        await sio.emit(
            "force_leave",
            {"reason": "sanction_timeout"},
            room=f"user:{uid}",
            namespace="/room",
        )

    details = f"Таймаут user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" duration={duration_label} reason={reason}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_timeout_add",
        details=details,
    )

    return Ok()


@log_route("admin.users.timeout_remove")
@require_roles_deco("admin")
@router.delete("/users/{user_id}/timeout", response_model=Ok)
async def revoke_user_timeout(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_TIMEOUT)
    if not active:
        raise HTTPException(status_code=404, detail="sanction_not_found")

    now = datetime.now(timezone.utc)
    active.revoked_at = now
    active.revoked_by_id = int(ident["id"])
    active.revoked_by_name = ident["username"]
    note = Notif(
        user_id=uid,
        title="Таймаут снят",
        text="Ваш таймаут снят досрочно. Доступ к комнатам восстановлен.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)

    details = f"Снятие таймаута user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_timeout_remove",
        details=details,
    )

    return Ok()


@log_route("admin.users.ban_add")
@require_roles_deco("admin")
@router.post("/users/{user_id}/ban", response_model=Ok)
async def apply_user_ban(user_id: int, payload: AdminSanctionBanIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_BAN)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    reason = payload.reason.strip()
    now = datetime.now(timezone.utc)
    sanction = UserSanction(
        user_id=uid,
        kind=SANCTION_BAN,
        reason=reason,
        issued_at=now,
        issued_by_id=int(ident["id"]),
        issued_by_name=ident["username"],
        duration_seconds=None,
        expires_at=None,
    )
    note = Notif(
        user_id=uid,
        title="Аккаунт забанен",
        text=f"Ваш аккаунт забанен. Причина: {reason}.",
    )
    session.add(sanction)
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)
        await sio.emit(
            "force_leave",
            {"reason": "sanction_ban"},
            room=f"user:{uid}",
            namespace="/room",
        )

    details = f"Бан user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" reason={reason}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_ban_add",
        details=details,
    )

    return Ok()


@log_route("admin.users.ban_remove")
@require_roles_deco("admin")
@router.delete("/users/{user_id}/ban", response_model=Ok)
async def revoke_user_ban(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_BAN)
    if not active:
        raise HTTPException(status_code=404, detail="sanction_not_found")

    now = datetime.now(timezone.utc)
    active.revoked_at = now
    active.revoked_by_id = int(ident["id"])
    active.revoked_by_name = ident["username"]
    note = Notif(
        user_id=uid,
        title="Бан снят",
        text="Ваш бан снят. Доступ к сайту восстановлен.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)

    details = f"Снятие бана user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_ban_remove",
        details=details,
    )

    return Ok()


@log_route("admin.users.suspend_add")
@require_roles_deco("admin")
@router.post("/users/{user_id}/suspend", response_model=Ok)
async def apply_user_suspend(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_SUSPEND)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    months = int(payload.months or 0)
    days = int(payload.days or 0)
    hours = int(payload.hours or 0)
    minutes = int(payload.minutes or 0)
    duration_seconds = compute_duration_seconds(months, days, hours, minutes)
    if duration_seconds <= 0:
        raise HTTPException(status_code=422, detail="duration_required")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=duration_seconds)
    reason = payload.reason.strip()
    duration_label = format_duration_parts(months, days, hours, minutes)

    sanction = UserSanction(
        user_id=uid,
        kind=SANCTION_SUSPEND,
        reason=reason,
        issued_at=now,
        issued_by_id=int(ident["id"]),
        issued_by_name=ident["username"],
        duration_seconds=duration_seconds,
        expires_at=expires_at,
    )
    note = Notif(
        user_id=uid,
        title="Ограничение",
        text=f"Доступ к играм ограничен на {duration_label}. Причина: {reason}.",
    )
    session.add(sanction)
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)

    details = f"SUSPEND user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" duration={duration_label} reason={reason}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_suspend_add",
        details=details,
    )

    return Ok()


@log_route("admin.users.suspend_remove")
@require_roles_deco("admin")
@router.delete("/users/{user_id}/suspend", response_model=Ok)
async def revoke_user_suspend(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_SUSPEND)
    if not active:
        raise HTTPException(status_code=404, detail="sanction_not_found")

    now = datetime.now(timezone.utc)
    active.revoked_at = now
    active.revoked_by_id = int(ident["id"])
    active.revoked_by_name = ident["username"]
    note = Notif(
        user_id=uid,
        title="Ограничение снято",
        text="Ограничение доступа к играм снято досрочно.",
    )
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "id": note.id,
                "title": note.title,
                "text": note.text,
                "date": note.created_at.isoformat(),
                "kind": "sanction",
                "ttl_ms": 15000,
                "read": False,
            },
            room=f"user:{uid}",
            namespace="/auth",
        )
        await emit_sanctions_update(session, uid)

    details = f"Снятие SUSPEND user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_suspend_remove",
        details=details,
    )

    return Ok()


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
