from __future__ import annotations
from typing import cast
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.clients import get_redis
from ...core.db import get_session
from ...models.log import AppLog
from ...models.room import Room
from ...models.user import User
from ...security.decorators import log_route, require_roles_deco
from ...security.parameters import ensure_app_settings, get_cached_settings, sync_cache_from_row
from ...schemas.admin import (
    AdminSettingsOut,
    SiteSettingsOut,
    SiteSettingsUpdateIn,
    GameSettingsOut,
    GameSettingsUpdateIn,
    PublicSettingsOut,
    SiteStatsOut,
    AdminLogOut,
    AdminLogsOut,
    AdminLogActionsOut,
    AdminRoomOut,
    AdminRoomsOut,
    AdminUserOut,
    AdminUsersOut,
    AdminUserRoleIn,
    AdminUserRoleOut,
)
from ..utils import (
    parse_month_range,
    parse_day_range,
    site_settings_out,
    game_settings_out,
    normalize_pagination,
    build_registrations_series,
    calc_total_stream_seconds,
    fetch_active_rooms_stats,
    fetch_online_users_count,
    fetch_user_avatar_map,
    fetch_user_name_avatar_maps,
    collect_room_user_ids,
    parse_room_game_params,
    build_room_user_stats,
    sum_room_stream_seconds,
    aggregate_user_room_stats,
)

router = APIRouter()


@log_route("admin.settings_public")
@router.get("/settings/public", response_model=PublicSettingsOut)
async def public_settings() -> PublicSettingsOut:
    settings = get_cached_settings()
    return PublicSettingsOut(
        registration_enabled=settings.registration_enabled,
        rooms_can_create=settings.rooms_can_create,
        games_can_start=settings.games_can_start,
    )


@log_route("admin.settings_get")
@require_roles_deco("admin")
@router.get("/settings", response_model=AdminSettingsOut)
async def get_settings(session: AsyncSession = Depends(get_session)) -> AdminSettingsOut:
    row = await ensure_app_settings(session)
    return AdminSettingsOut(site=site_settings_out(row), game=game_settings_out(row))


@log_route("admin.settings_site_update")
@require_roles_deco("admin")
@router.patch("/settings/site", response_model=SiteSettingsOut)
async def update_site_settings(payload: SiteSettingsUpdateIn, session: AsyncSession = Depends(get_session)) -> SiteSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    if data:
        await session.commit()
        await session.refresh(row)
    sync_cache_from_row(row)

    return site_settings_out(row)


@log_route("admin.settings_game_update")
@require_roles_deco("admin")
@router.patch("/settings/game", response_model=GameSettingsOut)
async def update_game_settings(payload: GameSettingsUpdateIn, session: AsyncSession = Depends(get_session)) -> GameSettingsOut:
    row = await ensure_app_settings(session)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    if data:
        await session.commit()
        await session.refresh(row)
    sync_cache_from_row(row)

    return game_settings_out(row)


@log_route("admin.stats")
@require_roles_deco("admin")
@router.get("/stats", response_model=SiteStatsOut)
async def site_stats(month: str | None = None, session: AsyncSession = Depends(get_session)) -> SiteStatsOut:
    start_dt, end_dt = parse_month_range(month)

    total_users = int(await session.scalar(select(func.count(User.id))) or 0)
    total_rooms = int(await session.scalar(select(func.count(Room.id))) or 0)
    registrations = await build_registrations_series(session, start_dt, end_dt)
    total_stream_seconds = await calc_total_stream_seconds(session)

    r = get_redis()
    active_rooms, active_room_users = await fetch_active_rooms_stats(r)
    online_users = await fetch_online_users_count(r)

    return SiteStatsOut(
        total_users=total_users,
        registrations=registrations,
        total_rooms=total_rooms,
        total_stream_minutes=total_stream_seconds // 60,
        active_rooms=active_rooms,
        active_room_users=active_room_users,
        online_users=online_users,
    )


@log_route("admin.logs.actions")
@require_roles_deco("admin")
@router.get("/logs/actions", response_model=AdminLogActionsOut)
async def log_actions(session: AsyncSession = Depends(get_session)) -> AdminLogActionsOut:
    rows = await session.execute(select(AppLog.action).distinct().order_by(AppLog.action))
    actions = [str(r[0]) for r in rows.all() if r and r[0] is not None]

    return AdminLogActionsOut(actions=actions)


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

    items: list[AdminRoomOut] = []
    for room in rooms:
        visitors_count = len(room.visitors or {})
        stream_seconds = sum_room_stream_seconds(room.screen_time)
        game_mode, game_format, spectators_limit = parse_room_game_params(room.game)
        visitors_items = build_room_user_stats(room.visitors, name_map, avatar_map)
        stream_items = build_room_user_stats(room.screen_time, name_map, avatar_map)

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
                game_mode=game_mode,
                game_format=game_format,
                spectators_limit=spectators_limit,
                visitors_count=visitors_count,
                visitors=visitors_items,
                stream_minutes=stream_seconds // 60,
                streamers=stream_items,
                has_stream=stream_seconds > 0,
            )
        )

    return AdminRoomsOut(total=total, items=items)


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
    rooms_created, room_seconds, stream_seconds = await aggregate_user_room_stats(session, ids)

    items = [
        AdminUserOut(
            id=int(u.id),
            username=u.username,
            avatar_name=u.avatar_name,
            role=u.role,
            registered_at=u.registered_at,
            last_login_at=u.last_login_at,
            last_visit_at=u.last_visit_at,
            rooms_created=rooms_created.get(int(u.id), 0),
            room_minutes=room_seconds.get(int(u.id), 0) // 60,
            stream_minutes=stream_seconds.get(int(u.id), 0) // 60,
        )
        for u in users
    ]

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
