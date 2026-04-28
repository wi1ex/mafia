from __future__ import annotations
from typing import cast
import asyncio
import structlog
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
from ...models.subscription import UserSubscription
from ...models.sanction import UserSanction
from ...models.user import User
from ...models.update import SiteUpdate, UpdateRead
from ...models.global_chat import GlobalChatMessage, GlobalChatMessageReaction
from ...core.logging import log_action
from ...realtime.sio import sio
from ...realtime.utils import (
    leave_room_atomic,
    stop_screen_for_user,
    emit_rooms_occupancy_safe,
    record_spectator_leave,
)
from ...security.decorators import log_route, require_protected_admin_dep
from ...security.auth_tokens import get_identity
from ...security.passwords import hash_password
from ...security.parameters import ensure_app_settings, sync_cache_from_row, refresh_app_settings, get_cached_settings
from ...services.livekit import remove_livekit_participant
from ...services.user_cache import refresh_user_profile_cache, get_user_profiles_cached
from ...services.profile_theme import (
    compute_subscription_end,
    compute_subscription_reduced_end,
    ensure_profile_theme_defaults,
    resolve_profile_theme_state,
    resolve_profile_theme_states,
)
from ...services.global_chat import (
    emit_global_chat_cleared,
    emit_global_chat_permissions_refresh,
    emit_global_chat_permissions_updated,
    emit_global_chat_role_notice,
    emit_global_chat_sanction_issued_notice,
    emit_global_chat_sanction_removed_notice,
)
from ...services.minio import CHAT_IMAGE_PREFIX, delete_chat_images_async, get_prefix_storage_stats_async
from ...schemas.common import Ok, Identity
from ...schemas.user import UserStatsOut
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
    AdminSanctionListItemOut,
    AdminSanctionsOut,
    AdminRoomOut,
    AdminRoomGameOut,
    AdminRoomsOut,
    AdminGameActionOut,
    AdminGameActionsOut,
    AdminGamePpkOut,
    AdminGamePpkUpdateIn,
    AdminGameResultUpdateIn,
    AdminGameResultOut,
    AdminUserOut,
    AdminUsersOut,
    AdminUserRoleIn,
    AdminUserRoleOut,
    AdminUserNameOut,
    AdminSubscriptionOut,
    AdminSubscriptionsOut,
    AdminSubscriptionCreateIn,
    AdminSubscriptionDurationIn,
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
    normalize_admin_banner_text,
    normalize_admin_banner_link,
    normalize_game_result,
    site_settings_out,
    game_settings_out,
    schedule_user_game_stats_cache_invalidation,
    normalize_pagination,
    build_registrations_series,
    build_registrations_monthly_series,
    build_games_series,
    build_games_monthly_series,
    build_active_users_series,
    build_active_users_monthly_series,
    calc_total_stream_seconds,
    calc_room_stream_seconds_in_range,
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
    build_user_stats_out,
    fetch_users_last_game_at,
    fetch_users_last_room_id,
    fetch_users_last_spectator_room_id,
    fetch_friends_count_for_users,
    fetch_sanction_counts_for_users,
    safe_int,
    normalizeGameActionsForUpdate,
    gameActionHasPpk,
    findGamePpkTargetUserId,
    findGameFoulDeathActionIndex,
    findGameFoulActionIndex,
    setGameActionPpk,
    game_action_fields,
    normalize_users_sort,
    admin_role_sort_key,
    admin_username_sort_key,
    user_sort_metric,
    compute_duration_seconds,
    gc_empty_room_and_emit,
    fetch_active_sanction,
    fetch_sanctions_for_users,
    is_sanction_active,
    build_admin_sanction_out,
    sanction_status,
    sanction_finished_at,
    sanction_served_seconds,
    sanction_actor_display,
    revoke_active_suspend,
    format_duration_parts,
    format_duration_seconds_compact,
    emit_notify,
    emit_sanctions_update,
    maybe_send_sanction_telegram_if_offline,
    refresh_rooms_after,
    set_user_deleted,
    delete_user_account_as_admin_action,
    broadcast_creator_rooms,
    force_leave_user_from_rooms,
    is_protected_admin,
    ensure_admin_target_allowed,
    ensure_admin_target_not_deleted,
    emit_rooms_upsert,
    emit_auth_profile_sync,
    emit_room_profile_theme_sync,
    notify_subscription_upsert,
    delete_gif_avatar_for_inactive_subscription,
    get_room_params_or_404,
)

public_router = APIRouter()
router = APIRouter(dependencies=[Depends(require_protected_admin_dep)])
log = structlog.get_logger()


@public_router.get("/settings/public", response_model=PublicSettingsOut)
@log_route("admin.settings_public")
async def public_settings(session: AsyncSession = Depends(get_session)) -> PublicSettingsOut:
    settings = await refresh_app_settings(session)
    return PublicSettingsOut(
        registration_enabled=settings.registration_enabled,
        rooms_can_create=settings.rooms_can_create,
        rooms_can_enter=settings.rooms_can_enter,
        games_can_start=settings.games_can_start,
        streams_can_start=settings.streams_can_start,
        chat_open_enabled=settings.chat_open_enabled,
        chat_messages_enabled=settings.chat_messages_enabled,
        verification_restrictions=settings.verification_restrictions,
        admin_banner_text=settings.admin_banner_text,
        admin_banner_link=settings.admin_banner_link,
        game_min_ready_players=settings.game_min_ready_players,
        winks_limit=settings.winks_limit,
        knocks_limit=settings.knocks_limit,
        wink_spot_chance_percent=settings.wink_spot_chance_percent,
        season_start_game_number=settings.season_start_game_number,
    )


@router.get("/settings", response_model=AdminSettingsOut)
@log_route("admin.settings_get")
async def get_settings(session: AsyncSession = Depends(get_session)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)

    return AdminSettingsOut(site=site_settings_out(row), game=game_settings_out(row))


@router.patch("/settings", response_model=AdminSettingsOut)
@log_route("admin.settings_update")
async def update_settings(payload: AdminSettingsUpdateIn, session: AsyncSession = Depends(get_session), ident: Identity = Depends(require_protected_admin_dep)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    site_data = data.get("site") or {}
    game_data = data.get("game") or {}
    incoming = {**site_data, **game_data}
    if "admin_banner_text" in incoming:
        incoming["admin_banner_text"] = normalize_admin_banner_text(incoming.get("admin_banner_text"))
    if "admin_banner_link" in incoming:
        incoming["admin_banner_link"] = normalize_admin_banner_link(incoming.get("admin_banner_link"))

    changed = {
        key: value
        for key, value in incoming.items()
        if getattr(row, key) != value
    }
    season_changed = "season_start_game_number" in changed

    for key, value in changed.items():
        setattr(row, key, value)

    if changed:
        await session.commit()
        await session.refresh(row)

    sync_cache_from_row(row)
    if changed:
        with suppress(Exception):
            await get_redis().publish("settings:update", "1")
        try:
            await sio.emit("settings_update", {"ok": True}, namespace="/auth")  
            await sio.emit("settings_update", {"ok": True}, namespace="/rooms")
        except Exception:
            pass
        with suppress(Exception):
            await emit_global_chat_permissions_refresh()
        if season_changed:
            schedule_user_game_stats_cache_invalidation("admin.settings.season_change.invalidate_stats_cache_failed")

    details = (
        f"Обновление настроек keys={','.join(sorted(changed))} season_changed={int(season_changed)}"
        if changed
        else "Обновление настроек без изменений"
    )
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_settings_update",
        details=details,
    )

    return AdminSettingsOut(site=site_settings_out(row), game=game_settings_out(row))


@router.get("/stats", response_model=SiteStatsOut)
@log_route("admin.stats")
async def site_stats(month: str | None = None, session: AsyncSession = Depends(get_session)) -> SiteStatsOut:
    start_dt, end_dt = parse_month_range(month)
    now = datetime.now(timezone.utc)
    month_start = start_dt
    month_end = end_dt if end_dt <= now else now
    if month_end < month_start:
        month_end = month_start

    total_users = int(await session.scalar(select(func.count(User.id)).where(User.deleted_at.is_(None))) or 0)
    (avatars_count, avatars_bytes), (images_count, images_bytes) = await asyncio.gather(
        get_prefix_storage_stats_async("avatars/"),
        get_prefix_storage_stats_async(CHAT_IMAGE_PREFIX),
    )
    total_rooms = int(await session.scalar(select(func.count(Room.id))) or 0)
    total_games = int(await session.scalar(select(func.count(Game.id))) or 0)
    registrations = await build_registrations_series(session, start_dt, end_dt)
    games_by_day = await build_games_series(session, start_dt, end_dt)
    active_users_by_day = await build_active_users_series(session, start_dt, end_dt)
    registrations_monthly = await build_registrations_monthly_series(session)
    games_monthly = await build_games_monthly_series(session)
    active_users_monthly = await build_active_users_monthly_series(session)
    total_stream_seconds = await calc_total_stream_seconds(session)
    month_stream_seconds = await calc_room_stream_seconds_in_range(session, month_start, month_end)

    r = get_redis()
    active_room_users = await fetch_active_rooms_stats(r)
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

    month_rooms = int(await session.scalar(select(func.count(Room.id)).where(Room.created_at >= month_start, Room.created_at < month_end)) or 0)
    month_games = int(await session.scalar(select(func.count(Game.id)).where(Game.finished_at >= month_start, Game.finished_at < month_end)) or 0)

    return SiteStatsOut(
        total_users=total_users,
        avatars_count=avatars_count,
        avatars_bytes=avatars_bytes,
        images_count=images_count,
        images_bytes=images_bytes,
        registrations=registrations,
        games_by_day=games_by_day,
        active_users_by_day=active_users_by_day,
        registrations_monthly=registrations_monthly,
        games_monthly=games_monthly,
        active_users_monthly=active_users_monthly,
        total_rooms=total_rooms,
        total_games=total_games,
        total_stream_minutes=total_stream_seconds // 60,
        active_room_users=active_room_users,
        online_users=online_users,
        online_users_list=online_users_list,
        last_month=PeriodStatsOut(
            games=month_games,
            rooms=month_rooms,
            stream_minutes=month_stream_seconds // 60,
        ),
    )


@router.get("/logs/actions", response_model=AdminLogActionsOut)
@log_route("admin.logs.actions")
async def log_actions(session: AsyncSession = Depends(get_session)) -> AdminLogActionsOut:
    rows = await session.execute(select(AppLog.action).distinct().order_by(AppLog.action))
    actions = {str(r[0]) for r in rows.all() if r and r[0] is not None}
    return AdminLogActionsOut(actions=sorted(actions))


@router.get("/logs", response_model=AdminLogsOut)
@log_route("admin.logs.list")
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


@router.get("/rooms", response_model=AdminRoomsOut)
@log_route("admin.rooms.list")
async def rooms_list(page: int = 1, limit: int = 20, username: str | None = None, room_filter: str | None = None, stream_only: bool | None = None, hidden_only: bool | None = None, has_games: bool | None = None, duo_only: bool | None = None, session: AsyncSession = Depends(get_session)) -> AdminRoomsOut:
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

    room_filter_value = (room_filter or "").strip().lower()
    if room_filter_value not in {"", "all", "stream_only", "hidden_only", "has_games", "duo_only"}:
        room_filter_value = "all"

    if room_filter_value in {"", "all"}:
        if stream_only:
            room_filter_value = "stream_only"
        elif hidden_only:
            room_filter_value = "hidden_only"
        elif has_games:
            room_filter_value = "has_games"
        elif duo_only:
            room_filter_value = "duo_only"
        else:
            room_filter_value = "all"

    if room_filter_value == "stream_only":
        filters.append(Room.screen_time != {})
    elif room_filter_value == "hidden_only":
        filters.append(Room.anonymity == "hidden")
    elif room_filter_value == "has_games":
        filters.append(select(Game.id).where(Game.room_id == Room.id).exists())
    elif room_filter_value == "duo_only":
        filters.append(Room.user_limit == 2)

    if filters:
        query = query.where(*filters)

    total = int(await session.scalar(select(func.count(Room.id)).where(*filters)) or 0)
    rows = await session.execute(query.order_by(Room.created_at.desc(), Room.id.desc()).offset(offset).limit(limit))
    rooms = rows.scalars().all()
    active_ids = [int(room.id) for room in rooms if room.deleted_at is None]
    live_stats: dict[int, dict] = {}
    if active_ids:
        try:
            live_stats = await fetch_live_room_stats(get_redis(), active_ids)
        except Exception:
            live_stats = {}

    def has_live_snapshot(stats) -> bool:
        if not isinstance(stats, dict):
            return False

        required = (
            "visitors",
            "spectators",
            "streams",
            "visitors_count",
            "spectators_count",
            "stream_seconds",
            "has_stream",
            "title",
            "user_limit",
            "creator",
            "creator_name",
            "created_at",
            "privacy",
            "anonymity",
            "game",
        )
        for key in required:
            if key not in stats:
                return False

        return True

    user_ids = collect_room_user_ids(rooms)
    for stats in live_stats.values():
        if not has_live_snapshot(stats):
            continue

        try:
            creator_id = int(stats.get("creator") or 0)
            if creator_id > 0:
                user_ids.add(creator_id)
        except Exception:
            pass
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
        if not has_live_snapshot(stats):
            stats = None

        visitors_map = stats["visitors"] if stats else (room.visitors or {})
        spectators_map = stats["spectators"] if stats else (room.spectators_time or {})
        stream_map = stats["streams"] if stats else (room.screen_time or {})
        visitors_count = stats["visitors_count"] if stats else len(room.visitors or {})
        spectators_count = stats["spectators_count"] if stats else len(room.spectators_time or {})
        stream_seconds = stats["stream_seconds"] if stats else sum_room_stream_seconds(room.screen_time)
        if stats:
            anonymity = "hidden" if str(stats.get("anonymity") or "visible") == "hidden" else "visible"
            creator = int(stats.get("creator") or room.creator)
            creator_name = str(stats.get("creator_name") or name_map.get(creator) or room.creator_name)
            creator_avatar_name = cast(str | None, stats.get("creator_avatar_name")) or avatar_map.get(creator)
            title = str(stats.get("title") or room.title)
            user_limit = int(stats.get("user_limit") or room.user_limit)
            privacy = "private" if str(stats.get("privacy") or room.privacy) == "private" else "open"
            raw_created_at = stats.get("created_at")
            if raw_created_at:
                try:
                    created_at = datetime.fromisoformat(str(raw_created_at).replace("Z", "+00:00"))
                except Exception:
                    created_at = room.created_at
            else:
                created_at = room.created_at
            game_params = parse_room_game_params(cast(dict | None, stats.get("game")) or room.game)
        else:
            anonymity = "hidden" if str(room.anonymity or "visible") == "hidden" else "visible"
            creator = int(room.creator)
            creator_name = cast(str, name_map.get(int(room.creator)) or room.creator_name)
            creator_avatar_name = avatar_map.get(int(room.creator))
            title = room.title
            user_limit = room.user_limit
            privacy = room.privacy
            created_at = room.created_at
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
                creator=creator,
                creator_name=creator_name,
                creator_avatar_name=creator_avatar_name,
                title=title,
                user_limit=user_limit,
                privacy=privacy,
                anonymity=anonymity,
                created_at=created_at,
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


@router.get("/games/{game_id}/actions", response_model=AdminGameActionsOut)
@log_route("admin.games.actions")
async def game_actions(game_id: int, session: AsyncSession = Depends(get_session)) -> AdminGameActionsOut:
    gid = safe_int(game_id)
    if gid <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    row = await session.execute(select(Game.id, Game.head_id, Game.seats, Game.actions, Game.result).where(Game.id == gid).limit(1))
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=404, detail="game_not_found")

    game_id_raw, head_id_raw, seats_raw, actions_raw, result_raw = rec
    game_id_value = safe_int(game_id_raw)
    if game_id_value <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    head_uid = safe_int(head_id_raw)
    uid_to_slot: dict[int, int] = {}
    if isinstance(seats_raw, dict):
        for raw_uid, raw_slot in seats_raw.items():
            uid = safe_int(raw_uid)
            slot = safe_int(raw_slot)
            if uid <= 0 or slot <= 0 or slot > 10 or uid in uid_to_slot:
                continue
            uid_to_slot[uid] = slot

    actions = normalizeGameActionsForUpdate(actions_raw)
    items: list[AdminGameActionOut] = []
    if actions:
        for index, raw_action in enumerate(actions, start=1):
            if not isinstance(raw_action, dict):
                continue
            action = dict(raw_action)
            title, summary, fields = game_action_fields(action, uid_to_slot=uid_to_slot, head_uid=head_uid)
            occurred_at: datetime | None = None
            ts = safe_int(action.get("ts"))
            if ts > 0:
                try:
                    occurred_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                except Exception:
                    occurred_at = None
            items.append(
                AdminGameActionOut(
                    order=index,
                    type=str(action.get("type") or "").strip().lower() or "unknown",
                    occurred_at=occurred_at,
                    title=title,
                    summary=summary,
                    fields=fields,
                )
            )

    return AdminGameActionsOut(
        id=game_id_value,
        number=game_id_value,
        result=normalize_game_result(result_raw),
        ppk_target_user_id=findGamePpkTargetUserId(actions),
        items=items,
    )


@router.patch("/games/{game_id}/result", response_model=AdminGameResultOut)
@log_route("admin.games.result_update")
async def update_game_result(game_id: int, payload: AdminGameResultUpdateIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminGameResultOut:
    gid = safe_int(game_id)
    if gid <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    game = await session.get(Game, gid)
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    prev_result_raw = str(getattr(game, "result", "") or "").strip().lower()
    prev_result = normalize_game_result(prev_result_raw)
    next_result = payload.result

    if prev_result_raw != next_result:
        game.result = next_result
        await log_action(
            session,
            user_id=int(ident["id"]),
            username=ident["username"],
            action="admin_game_result_update",
            details=f"Изменение результата игры game_id={gid} from={prev_result} to={next_result}",
            commit=False,
        )
        await session.commit()
        await session.refresh(game)
        schedule_user_game_stats_cache_invalidation(
            "admin.games.result_update.invalidate_stats_cache_failed",
            game_id=gid,
        )

    return AdminGameResultOut(
        id=gid,
        number=gid,
        result=normalize_game_result(getattr(game, "result", None)),
    )


@router.patch("/games/{game_id}/ppk", response_model=AdminGamePpkOut)
@log_route("admin.games.ppk_update")
async def update_game_ppk(game_id: int, payload: AdminGamePpkUpdateIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminGamePpkOut:
    gid = safe_int(game_id)
    if gid <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    game = await session.get(Game, gid)
    if not game:
        raise HTTPException(status_code=404, detail="game_not_found")

    original_actions = getattr(game, "actions", None)
    original_actions_list = original_actions if isinstance(original_actions, list) else []
    actions = normalizeGameActionsForUpdate(original_actions_list)
    prev_target_user_id = findGamePpkTargetUserId(actions)

    next_target_user_id: int | None = None
    if payload.target_user_id is not None:
        requested_target_uid = safe_int(payload.target_user_id)
        if requested_target_uid <= 0:
            raise HTTPException(status_code=422, detail="ppk_target_invalid")

        if findGameFoulDeathActionIndex(actions, requested_target_uid) is None:
            raise HTTPException(status_code=409, detail="ppk_target_not_foul_removed")

        next_target_user_id = requested_target_uid

    for raw_action in actions:
        if not isinstance(raw_action, dict):
            continue
        action_type = str(raw_action.get("type") or "").strip().lower()
        if action_type not in {"death", "foul"}:
            continue
        if gameActionHasPpk(raw_action):
            setGameActionPpk(raw_action, False)

    if next_target_user_id is not None:
        death_action_index = findGameFoulDeathActionIndex(actions, next_target_user_id)
        if death_action_index is None:
            raise HTTPException(status_code=409, detail="ppk_target_not_foul_removed")

        death_action = actions[death_action_index]
        if isinstance(death_action, dict):
            setGameActionPpk(death_action, True)

        foul_action_index = findGameFoulActionIndex(actions, next_target_user_id)
        if foul_action_index is not None:
            foul_action = actions[foul_action_index]
            if isinstance(foul_action, dict):
                setGameActionPpk(foul_action, True)

    changed = actions != original_actions_list
    actual_target_user_id = findGamePpkTargetUserId(actions)

    if changed:
        game.actions = actions
        await log_action(
            session,
            user_id=int(ident["id"]),
            username=ident["username"],
            action="admin_game_ppk_update",
            details=(
                f"Изменение ППК игры game_id={gid} "
                f"from_user_id={prev_target_user_id or 0} to_user_id={actual_target_user_id or 0}"
            ),
            commit=False,
        )
        await session.commit()
        schedule_user_game_stats_cache_invalidation(
            "admin.games.ppk_update.invalidate_stats_cache_failed",
            game_id=gid,
        )

    return AdminGamePpkOut(
        id=gid,
        number=gid,
        target_user_id=actual_target_user_id,
    )


@router.post("/rooms/{room_id}/close", response_model=Ok)
@log_route("admin.rooms.close")
async def room_close(room_id: int, ident: Identity = Depends(require_protected_admin_dep), session: AsyncSession = Depends(get_session)) -> Ok:
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
            await r.delete(
                f"room:{room_id}:user:{uid}:epoch",
                f"room:{room_id}:user:{uid}:bg_state",
                f"room:{room_id}:user:{uid}:sid",
            )
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
        with suppress(Exception):
            await remove_livekit_participant(rid=room_id, uid=uid)

    for uid in spectator_ids - member_ids:
        await sio.emit("force_leave",
                       {"room_id": room_id, "reason": "room_deleted"},
                       room=f"user:{uid}",
                       namespace="/room")
        with suppress(Exception):
            await remove_livekit_participant(rid=room_id, uid=uid)
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

    spectator_only_count = len(spectator_ids - member_ids)
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_room_close",
        details=(
            f"Закрытие комнаты room_id={room_id} phase={phase} "
            f"members={len(member_ids)} spectators={spectator_only_count}"
        ),
    )

    return Ok()


@router.post("/rooms/kick", response_model=Ok)
@log_route("admin.rooms.kick_all")
async def rooms_kick_all(ident: Identity = Depends(require_protected_admin_dep), session: AsyncSession = Depends(get_session)) -> Ok:
    r = get_redis()
    try:
        room_ids_raw = await r.zrange("rooms:index", 0, -1)
    except Exception:
        room_ids_raw = []

    processed_rooms = 0
    total_member_ids = 0
    total_spectator_ids = 0

    for raw_id in room_ids_raw:
        try:
            rid = int(raw_id)
        except Exception:
            continue
        processed_rooms += 1

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
        total_member_ids += len(member_ids)
        total_spectator_ids += len(spectator_ids - member_ids)

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
                await r.delete(
                    f"room:{rid}:user:{uid}:epoch",
                    f"room:{rid}:user:{uid}:bg_state",
                    f"room:{rid}:user:{uid}:sid",
                )
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
            with suppress(Exception):
                await remove_livekit_participant(rid=rid, uid=uid)

        for uid in spectator_ids - member_ids:
            await sio.emit("force_leave",
                           {"room_id": rid, "reason": "admin_kick_all"},
                           room=f"user:{uid}",
                           namespace="/room")
            with suppress(Exception):
                await remove_livekit_participant(rid=rid, uid=uid)
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

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_rooms_kick_all",
        details=(
            f"Принудительное освобождение всех комнат rooms={processed_rooms} "
            f"members={total_member_ids} spectators={total_spectator_ids}"
        ),
    )

    return Ok()


@router.post("/chat/clear", response_model=Ok)
@log_route("admin.global_chat.clear")
async def clear_global_chat(ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    messages_count = int(await session.scalar(select(func.count(GlobalChatMessage.id))) or 0)
    reactions_count = int(await session.scalar(select(func.count(GlobalChatMessageReaction.message_id))) or 0)

    await session.execute(delete(GlobalChatMessageReaction))
    await session.execute(delete(GlobalChatMessage))
    await session.commit()

    try:
        images_detail = str(await delete_chat_images_async())
    except Exception:
        images_detail = "error"
        log.exception("admin.global_chat.clear.chat_images_delete_failed")

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_global_chat_clear",
        details=f"Очистка общего чата messages={messages_count} reactions={reactions_count} images={images_detail}",
    )

    with suppress(Exception):
        await emit_global_chat_cleared()

    return Ok()


@router.get("/users", response_model=AdminUsersOut)
@log_route("admin.users.list")
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
    last_game_at: dict[int, datetime | None]
    last_room_id: dict[int, int | None]
    last_spectator_room_id: dict[int, int | None]

    if sort_key in {"registered_at", "last_login_at", "last_visit_at"}:
        if sort_key == "last_login_at":
            sort_expr = User.last_login_at.desc()
        elif sort_key == "last_visit_at":
            sort_expr = User.last_visit_at.desc()
        else:
            sort_expr = User.registered_at.desc()

        total = int(await session.scalar(select(func.count(User.id)).where(*filters)) or 0)
        rows = await session.execute(select(User).where(*filters).order_by(sort_expr, User.id.desc()).offset(offset).limit(limit))
        users = rows.scalars().all()
        ids = [int(u.id) for u in users]
        friends_count = await fetch_friends_count_for_users(session, ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = await aggregate_user_room_stats(session, ids)
        last_game_at = await fetch_users_last_game_at(session, ids)
        last_room_id = await fetch_users_last_room_id(session, ids)
        last_spectator_room_id = await fetch_users_last_spectator_room_id(session, ids)
    else:
        rows = await session.execute(select(User).where(*filters))
        all_users = rows.scalars().all()
        total = len(all_users)
        all_ids = [int(u.id) for u in all_users]
        tg_invites_enabled = {int(u.id): (u.tg_invites_enabled is not False) for u in all_users}
        friends_count = await fetch_friends_count_for_users(session, all_ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = await aggregate_user_room_stats(session, all_ids)
        sanction_counts = await fetch_sanction_counts_for_users(session, all_ids)
        if sort_key == "last_game_at":
            all_last_game_at = await fetch_users_last_game_at(session, all_ids)
            last_game_at_ts = {uid: int(game_dt.timestamp()) if game_dt else 0 for uid, game_dt in all_last_game_at.items()}
        else:
            all_last_game_at = {}
            last_game_at_ts = {}
        if sort_key == "last_room_id":
            all_last_room_id = await fetch_users_last_room_id(session, all_ids)
        else:
            all_last_room_id = {}
        if sort_key == "last_spectator_room_id":
            all_last_spectator_room_id = await fetch_users_last_spectator_room_id(session, all_ids)
        else:
            all_last_spectator_room_id = {}

        if sort_key == "role":
            users_sorted = sorted(
                all_users,
                key=lambda u: (
                    admin_role_sort_key(u.role),
                    admin_username_sort_key(u.username),
                    -int(u.registered_at.timestamp()),
                    -int(u.id),
                ),
            )
        elif sort_key == "username":
            users_sorted = sorted(
                all_users,
                key=lambda u: (
                    admin_username_sort_key(u.username),
                    admin_role_sort_key(u.role),
                    -int(u.registered_at.timestamp()),
                    -int(u.id),
                ),
            )
        else:
            users_sorted = sorted(
                all_users,
                key=lambda u: (
                    user_sort_metric(
                        sort_by=sort_key,
                        uid=int(u.id),
                        tg_invites_enabled=tg_invites_enabled,
                        friends_count=friends_count,
                        rooms_created=rooms_created,
                        room_seconds=room_seconds,
                        stream_seconds=stream_seconds,
                        games_played=games_played,
                        games_hosted=games_hosted,
                        spectator_seconds=spectator_seconds,
                        sanction_counts=sanction_counts,
                        last_game_at_ts=last_game_at_ts,
                        last_room_id=all_last_room_id,
                        last_spectator_room_id=all_last_spectator_room_id,
                    ),
                    u.registered_at,
                    int(u.id),
                ),
                reverse=True,
            )
        users = users_sorted[offset:offset + limit]
        ids = [int(u.id) for u in users]
        if sort_key == "last_game_at":
            last_game_at = {uid: all_last_game_at.get(uid) for uid in ids}
        else:
            last_game_at = await fetch_users_last_game_at(session, ids)
        if sort_key == "last_room_id":
            last_room_id = {uid: all_last_room_id.get(uid) for uid in ids}
        else:
            last_room_id = await fetch_users_last_room_id(session, ids)
        if sort_key == "last_spectator_room_id":
            last_spectator_room_id = {uid: all_last_spectator_room_id.get(uid) for uid in ids}
        else:
            last_spectator_room_id = await fetch_users_last_spectator_room_id(session, ids)

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
            tg_id=u.telegram_id,
            username=u.username,
            avatar_name=u.avatar_name,
            role=u.role,
            telegram_verified=bool(u.telegram_id),
            tg_invites_enabled=(u.tg_invites_enabled is not False),
            has_password=bool(u.password_hash),
            protected_user=is_protected_admin(uid),
            registered_at=u.registered_at,
            last_login_at=u.last_login_at,
            last_visit_at=u.last_visit_at,
            last_game_at=last_game_at.get(uid),
            last_room_id=last_room_id.get(uid),
            last_spectator_room_id=last_spectator_room_id.get(uid),
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


@router.get("/sanctions", response_model=AdminSanctionsOut)
@log_route("admin.sanctions.list")
async def sanctions_list(page: int = 1, limit: int = 20, username: str | None = None, session: AsyncSession = Depends(get_session)) -> AdminSanctionsOut:
    limit, page, offset = normalize_pagination(page, limit)

    filters = []
    if username:
        needle = username.lower()
        filters.append(func.lower(User.username).contains(needle, autoescape=True))

    total = int(
        await session.scalar(
            select(func.count(UserSanction.id))
            .select_from(UserSanction)
            .outerjoin(User, User.id == UserSanction.user_id)
            .where(*filters)
        ) or 0
    )

    rows = await session.execute(
        select(UserSanction, User.username)
        .select_from(UserSanction)
        .outerjoin(User, User.id == UserSanction.user_id)
        .where(*filters)
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
        .offset(offset)
        .limit(limit)
    )

    now = datetime.now(timezone.utc)
    items: list[AdminSanctionListItemOut] = []
    for row, target_username in rows.all():
        sanction = cast(UserSanction, row)
        uid = cast(int, sanction.user_id)
        sid = cast(int, sanction.id)
        issued_by_id = cast(int, sanction.issued_by_id) if sanction.issued_by_id is not None else None
        revoked_by_id = cast(int, sanction.revoked_by_id) if sanction.revoked_by_id is not None else None
        status = sanction_status(sanction, now)
        revoked_by_display: str | None = None
        if status == "expired_auto":
            revoked_by_display = "авто"
        elif sanction.revoked_at is not None:
            revoked_by_display = sanction_actor_display(sanction.revoked_by_name, revoked_by_id, auto_fallback=True)

        items.append(
            AdminSanctionListItemOut(
                id=sid,
                user_id=uid,
                username=cast(str | None, target_username),
                kind=cast(str, sanction.kind),
                status=cast(str, status),
                issued_at=sanction.issued_at,
                finished_at=sanction_finished_at(sanction),
                issued_by_id=issued_by_id,
                issued_by_name=sanction.issued_by_name,
                issued_by_display=sanction_actor_display(sanction.issued_by_name, issued_by_id),
                revoked_by_id=revoked_by_id,
                revoked_by_name=sanction.revoked_by_name,
                revoked_by_display=revoked_by_display,
                duration_seconds=sanction.duration_seconds,
                served_seconds=sanction_served_seconds(sanction, now),
                reason=sanction.reason or None,
            )
        )

    return AdminSanctionsOut(total=total, items=items)


@router.get("/subscriptions", response_model=AdminSubscriptionsOut)
@log_route("admin.subscriptions.list")
async def subscriptions_list(session: AsyncSession = Depends(get_session)) -> AdminSubscriptionsOut:
    now = datetime.now(timezone.utc)
    rows = await session.execute(select(UserSubscription))
    subscriptions = rows.scalars().all()
    if not subscriptions:
        return AdminSubscriptionsOut(items=[])

    user_ids = [int(row.user_id) for row in subscriptions if row.user_id is not None]
    profiles = await get_user_profiles_cached(session, user_ids)
    theme_states = await resolve_profile_theme_states(session, user_ids, now=now)

    items: list[AdminSubscriptionOut] = []
    for row in subscriptions:
        if row.user_id is None:
            continue
        uid = int(row.user_id)
        profile = profiles.get(uid) or {}
        theme_state = theme_states.get(uid)
        is_active = row.starts_at <= now < row.ends_at
        items.append(
            AdminSubscriptionOut(
                user_id=uid,
                username=cast(str | None, profile.get("username")),
                avatar_name=cast(str | None, profile.get("avatar_name")),
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                is_active=is_active,
                profile_theme_color=theme_state.color if theme_state else None,
                profile_theme_icon=theme_state.icon if theme_state else None,
            )
        )
    items.sort(
        key=lambda item: (
            0 if item.is_active else 1,
            item.ends_at if item.is_active else -item.ends_at.timestamp(),
            str(item.username or f"user{item.user_id}").lower(),
            item.user_id,
        )
    )
    return AdminSubscriptionsOut(items=items)


@router.post("/subscriptions", response_model=AdminSubscriptionOut)
@log_route("admin.subscriptions.upsert")
async def subscriptions_upsert(payload: AdminSubscriptionCreateIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminSubscriptionOut:
    months = int(payload.months or 0)
    days = int(payload.days or 0)
    if months <= 0 and days <= 0:
        raise HTTPException(status_code=422, detail="duration_required")

    user = await session.get(User, int(payload.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_not_deleted(user)

    uid = int(user.id)
    now = datetime.now(timezone.utc)
    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == uid).limit(1)
    )

    had_subscription = subscription is not None
    had_active_subscription = False
    if subscription is None:
        starts_at = now
        ends_at = compute_subscription_end(starts_at, months=months, days=days)
        subscription = UserSubscription(user_id=uid, starts_at=starts_at, ends_at=ends_at)
        session.add(subscription)
    else:
        had_active_subscription = subscription.starts_at <= now < subscription.ends_at
        if had_active_subscription:
            subscription.ends_at = compute_subscription_end(subscription.ends_at, months=months, days=days)
        else:
            subscription.starts_at = now
            subscription.ends_at = compute_subscription_end(now, months=months, days=days)

    await ensure_profile_theme_defaults(session, uid, now=now)

    await session.commit()
    await session.refresh(subscription)
    await refresh_user_profile_cache(session, uid)
    theme_state = await resolve_profile_theme_state(session, uid)

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_subscription_upsert",
        details=(
            f"Подписка user_id={uid} username={user.username or f'user{uid}'} "
            f"months={months} days={days} starts_at={subscription.starts_at.isoformat()} "
            f"ends_at={subscription.ends_at.isoformat()}"
        ),
    )

    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        from ...services.global_chat import emit_global_chat_profile_theme_sync
        await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    try:
        await notify_subscription_upsert(session, user, subscription, extended=had_subscription)
    except Exception as exc:
        log.warning(
            "admin.subscription.notify_failed",
            uid=uid,
            extended=had_subscription,
            err=type(exc).__name__,
        )

    return AdminSubscriptionOut(
        user_id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        is_active=True,
        profile_theme_color=theme_state.color,
        profile_theme_icon=theme_state.icon,
    )


@router.patch("/subscriptions/{user_id}/reduce", response_model=AdminSubscriptionOut)
@log_route("admin.subscriptions.reduce")
async def subscriptions_reduce(user_id: int, payload: AdminSubscriptionDurationIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminSubscriptionOut:
    months = int(payload.months or 0)
    days = int(payload.days or 0)
    if months <= 0 and days <= 0:
        raise HTTPException(status_code=422, detail="duration_required")

    uid = int(user_id)
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_not_deleted(user)

    now = datetime.now(timezone.utc)
    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == uid).limit(1)
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription_not_found")

    if not (subscription.starts_at <= now < subscription.ends_at):
        raise HTTPException(status_code=422, detail="subscription_not_active")

    next_ends_at = compute_subscription_reduced_end(
        subscription.ends_at,
        months=months,
        days=days,
    )
    if next_ends_at <= now:
        raise HTTPException(status_code=422, detail="subscription_reduce_too_large")

    previous_ends_at = subscription.ends_at
    subscription.ends_at = next_ends_at

    await ensure_profile_theme_defaults(session, uid, now=now)

    await session.commit()
    await session.refresh(subscription)
    await refresh_user_profile_cache(session, uid)
    theme_state = await resolve_profile_theme_state(session, uid)

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_subscription_reduce",
        details=(
            f"Подписка уменьшена user_id={uid} username={user.username or f'user{uid}'} "
            f"months={months} days={days} starts_at={subscription.starts_at.isoformat()} "
            f"old_ends_at={previous_ends_at.isoformat()} "
            f"ends_at={subscription.ends_at.isoformat()}"
        ),
    )

    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        from ...services.global_chat import emit_global_chat_profile_theme_sync
        await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)

    return AdminSubscriptionOut(
        user_id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        is_active=True,
        profile_theme_color=theme_state.color,
        profile_theme_icon=theme_state.icon,
    )


@router.delete("/subscriptions/{user_id}", response_model=Ok)
@log_route("admin.subscriptions.delete")
async def subscriptions_delete(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(user_id)
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == uid).limit(1)
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription_not_found")

    await session.delete(subscription)
    await session.commit()
    avatar_deleted = await delete_gif_avatar_for_inactive_subscription(session, uid)
    if not avatar_deleted:
        await refresh_user_profile_cache(session, uid)

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_subscription_delete",
        details=f"Подписка снята user_id={uid} username={user.username or f'user{uid}'}",
    )

    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(uid, None, None)
    with suppress(Exception):
        from ...services.global_chat import emit_global_chat_profile_theme_sync
        await emit_global_chat_profile_theme_sync(uid, None, None)

    return Ok()


@router.get("/users/{user_id}/stats", response_model=UserStatsOut)
@log_route("admin.users.stats")
async def user_stats(user_id: int, season: int | None = None, session: AsyncSession = Depends(get_session)) -> UserStatsOut:
    uid = int(user_id)
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    return await build_user_stats_out(session, uid, season)


@router.patch("/users/{user_id}/role", response_model=AdminUserRoleOut)
@log_route("admin.users.role")
async def update_user_role(user_id: int, payload: AdminUserRoleIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminUserRoleOut:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
    prev_role = user.role
    if prev_role == "admin" or payload.role == "admin":
        raise HTTPException(status_code=403, detail="admin_role_locked")

    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    await refresh_user_profile_cache(session, int(user.id))

    uid = cast(int, user.id)
    if prev_role != user.role:
        if user.role == "moder":
            action = "moder_role_grant"
        elif prev_role == "moder":
            action = "moder_role_revoke"
        else:
            action = "role_update"
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

        if user.role == "moder":
            note = Notif(
                user_id=uid,
                title="Новая роль",
                text="Вам выдана роль Модератор.",
            )
            session.add(note)
            await session.commit()
            await session.refresh(note)
            with suppress(Exception):
                await emit_notify(uid, note, kind="role_update")
            with suppress(Exception):
                await emit_global_chat_role_notice(
                    session,
                    actor_user_id=int(ident["id"]),
                    target_user_id=uid,
                    target_username=user.username,
                    role="moder",
                    granted=True,
                )
        elif prev_role == "moder":
            note = Notif(
                user_id=uid,
                title="Новая роль",
                text="С вас снята роль Модератор.",
            )
            session.add(note)
            await session.commit()
            await session.refresh(note)
            with suppress(Exception):
                await emit_notify(uid, note, kind="role_update")
            with suppress(Exception):
                await emit_global_chat_role_notice(
                    session,
                    actor_user_id=int(ident["id"]),
                    target_user_id=uid,
                    target_username=user.username,
                    role="moder",
                    granted=False,
                )

    return AdminUserRoleOut(id=uid, role=user.role)


@router.post("/users/{user_id}/nickname_reset", response_model=AdminUserNameOut)
@log_route("admin.users.nickname_reset")
async def reset_user_nickname(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminUserNameOut:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
    uid = int(user.id)
    next_username = f"user_{uid}"
    if str(user.username) == next_username:
        return AdminUserNameOut(id=uid, username=next_username)

    conflict = await session.scalar(select(User.id).where(func.lower(User.username) == next_username.lower(), User.id != uid).limit(1))
    if conflict:
        raise HTTPException(status_code=409, detail="username_taken")

    prev_username = str(user.username)
    user.username = next_username
    await session.commit()
    await session.refresh(user)
    await refresh_user_profile_cache(session, uid)
    with suppress(Exception):
        await broadcast_creator_rooms(uid, update_name=str(user.username))

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="admin_nickname_reset",
        details=f"Nickname reset user_id={uid} from={prev_username} to={next_username}",
    )

    return AdminUserNameOut(id=uid, username=next_username)


@router.post("/users/{user_id}/delete", response_model=Ok)
@log_route("admin.users.account_delete")
async def delete_user_account(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    await delete_user_account_as_admin_action(
        session,
        int(user_id),
        actor_user_id=int(ident["id"]),
        actor_username=ident["username"],
    )
    return Ok()


@router.post("/users/{user_id}/restore", response_model=Ok)
@log_route("admin.users.account_restore")
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


@router.post("/users/{user_id}/unverify", response_model=Ok)
@log_route("admin.users.unverify")
async def unverify_user(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
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
    with suppress(Exception):
        await emit_global_chat_permissions_updated(uid)
    return Ok()


@router.post("/users/{user_id}/password_clear", response_model=Ok)
@log_route("admin.users.password_clear")
async def clear_user_password(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
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


@router.post("/users/{user_id}/timeout", response_model=Ok)
@log_route("admin.users.timeout_add")
async def apply_user_timeout(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
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
        telegram_id_snapshot=user.telegram_id,
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
        text=f"Вам выдан таймаут на {duration_label}. Причина: {reason}",
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
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, telegram_id=user.telegram_id, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        await emit_global_chat_sanction_issued_notice(
            session,
            actor_user_id=int(ident["id"]),
            target_user_id=uid,
            target_username=user.username,
            kind=SANCTION_TIMEOUT,
            reason=reason,
            duration_label=duration_label,
        )
    with suppress(Exception):
        await force_leave_user_from_rooms(uid, reason="sanction_timeout")

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


@router.delete("/users/{user_id}/timeout", response_model=Ok)
@log_route("admin.users.timeout_remove")
async def revoke_user_timeout(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_TIMEOUT)
    if not active:
        raise HTTPException(status_code=404, detail="sanction_not_found")

    now = datetime.now(timezone.utc)
    remaining_duration_label = None
    if active.expires_at is not None:
        remaining_seconds = int((active.expires_at - now).total_seconds())
        if remaining_seconds > 0:
            remaining_duration_label = format_duration_seconds_compact(remaining_seconds)
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
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, telegram_id=user.telegram_id, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        await emit_global_chat_sanction_removed_notice(
            session,
            actor_user_id=int(ident["id"]),
            target_user_id=uid,
            target_username=user.username,
            kind=SANCTION_TIMEOUT,
            reason=active.reason or "",
            source="admin",
            remaining_duration_label=remaining_duration_label,
        )

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


@router.post("/users/{user_id}/ban", response_model=Ok)
@log_route("admin.users.ban_add")
async def apply_user_ban(user_id: int, payload: AdminSanctionBanIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_BAN)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    reason = payload.reason.strip()
    now = datetime.now(timezone.utc)
    sanction = UserSanction(
        user_id=uid,
        telegram_id_snapshot=user.telegram_id,
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
        text=f"Ваш аккаунт забанен. Причина: {reason}",
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
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, telegram_id=user.telegram_id, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        await emit_global_chat_sanction_issued_notice(
            session,
            actor_user_id=int(ident["id"]),
            target_user_id=uid,
            target_username=user.username,
            kind=SANCTION_BAN,
            reason=reason,
            duration_label=None,
        )
    with suppress(Exception):
        await force_leave_user_from_rooms(uid, reason="sanction_ban")

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


@router.delete("/users/{user_id}/ban", response_model=Ok)
@log_route("admin.users.ban_remove")
async def revoke_user_ban(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
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
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, telegram_id=user.telegram_id, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        await emit_global_chat_sanction_removed_notice(
            session,
            actor_user_id=int(ident["id"]),
            target_user_id=uid,
            target_username=user.username,
            kind=SANCTION_BAN,
            reason=active.reason or "",
            source="admin",
        )

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


@router.post("/users/{user_id}/suspend", response_model=Ok)
@log_route("admin.users.suspend_add")
async def apply_user_suspend(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
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
        telegram_id_snapshot=user.telegram_id,
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
        title="Отстранение от игр",
        text=(
            f"Доступ к играм ограничен на {duration_label}. Причина: {reason} "
            "Вы можете проводить игры: после каждой проведенной вами игры срок отстранения от игр будет уменьшаться на 6 часов."
        ),
    )
    session.add(sanction)
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        r = get_redis()
        raw_room_id = await r.get(f"user:{uid}:room")
        room_id = int(raw_room_id) if raw_room_id else 0
        if room_id > 0 and await r.srem(f"room:{room_id}:ready", str(uid)):
            await sio.emit(
                "state_changed",
                {"user_id": uid, "ready": "0"},
                room=f"room:{room_id}",
                namespace="/room",
            )

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
    with suppress(Exception):
        await maybe_send_sanction_telegram_if_offline(session, user_id=uid, telegram_id=user.telegram_id, note=note)
    with suppress(Exception):
        await emit_sanctions_update(session, uid)
    with suppress(Exception):
        await emit_global_chat_sanction_issued_notice(
            session,
            actor_user_id=int(ident["id"]),
            target_user_id=uid,
            target_username=user.username,
            kind=SANCTION_SUSPEND,
            reason=reason,
            duration_label=duration_label,
        )

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


@router.delete("/users/{user_id}/suspend", response_model=Ok)
@log_route("admin.users.suspend_remove")
async def revoke_user_suspend(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    ensure_admin_target_allowed(user)
    ensure_admin_target_not_deleted(user)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_SUSPEND)
    if not active:
        raise HTTPException(status_code=404, detail="sanction_not_found")

    await revoke_active_suspend(
        session,
        active,
        revoked_by_id=int(ident["id"]),
        revoked_by_name=ident["username"],
        note_text="Отстранение от игр снято досрочно.",
    )

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


@router.get("/updates", response_model=AdminUpdatesOut)
@log_route("admin.updates.list")
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


@router.post("/updates", response_model=AdminUpdateOut)
@log_route("admin.updates.create")
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


@router.patch("/updates/{update_id}", response_model=AdminUpdateOut)
@log_route("admin.updates.update")
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


@router.delete("/updates/{update_id}", response_model=Ok)
@log_route("admin.updates.delete")
async def updates_delete(update_id: int, session: AsyncSession = Depends(get_session)) -> Ok:
    row = await session.get(SiteUpdate, int(update_id))
    if not row:
        raise HTTPException(status_code=404, detail="update_not_found")

    await session.execute(delete(UpdateRead).where(UpdateRead.update_id == int(update_id)))
    await session.delete(row)
    await session.commit()
    return Ok()
