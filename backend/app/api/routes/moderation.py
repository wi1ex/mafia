from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import cast
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.clients import get_redis
from ...core.db import get_session
from ...core.logging import log_action
from ...core.roles import ROLE_USER
from ...models.notif import Notif
from ...models.sanction import UserSanction
from ...models.user import User
from ...schemas.admin import AdminSanctionTimedIn
from ...schemas.common import Identity, Ok
from ...schemas.moderation import ModerationUserOut, ModerationUsersOut
from ...schemas.user import UserStatsOut, UserTopPlayerOut
from ...realtime.sio import sio
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, require_roles_deco
from ...services.global_chat import emit_global_chat_sanction_issued_notice
from ...services.user_stats import get_user_game_stats_cached
from ...services.user_cache import get_user_profiles_cached
from ..utils import (
    SANCTION_SUSPEND,
    admin_username_sort_key,
    aggregate_user_games_in_owned_rooms_stats,
    aggregate_user_room_stats,
    aggregate_user_room_time_stats,
    build_admin_sanction_out,
    compute_duration_seconds,
    emit_notify,
    emit_sanctions_update,
    get_moderation_target_user,
    fetch_active_sanction,
    fetch_friends_count_for_users,
    fetch_sanction_counts_for_users,
    fetch_sanctions_for_users,
    fetch_users_last_game_at,
    format_duration_parts,
    is_sanction_active,
    normalize_pagination,
    normalize_moderation_users_sort,
    revoke_active_suspend,
    user_sort_metric,
)

router = APIRouter()


@log_route("moderation.users.list")
@require_roles_deco("moder")
@router.get("/users", response_model=ModerationUsersOut)
async def moderation_users_list(page: int = 1, limit: int = 20, username: str | None = None, sort_by: str | None = None, session: AsyncSession = Depends(get_session)) -> ModerationUsersOut:
    limit, page, offset = normalize_pagination(page, limit)
    sort_key = normalize_moderation_users_sort(sort_by)

    filters = [User.deleted_at.is_(None), User.role == ROLE_USER]
    if username:
        needle = username.lower()
        filters.append(func.lower(User.username).contains(needle, autoescape=True))

    users: list[User]

    if sort_key in {"registered_at", "last_login_at", "last_visit_at"}:
        if sort_key == "last_login_at":
            sort_expr = User.last_login_at.desc()
        elif sort_key == "last_visit_at":
            sort_expr = User.last_visit_at.desc()
        else:
            sort_expr = User.registered_at.desc()

        total = int(await session.scalar(select(func.count(User.id)).where(*filters)) or 0)
        rows = await session.execute(
            select(User).where(*filters).order_by(sort_expr, User.id.desc()).offset(offset).limit(limit)
        )
        users = list(rows.scalars().all())
        ids = [int(u.id) for u in users]
        friends_count = await fetch_friends_count_for_users(session, ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = (
            await aggregate_user_room_stats(session, ids)
        )
        last_game_at = await fetch_users_last_game_at(session, ids)
    else:
        rows = await session.execute(select(User).where(*filters))
        all_users = list(rows.scalars().all())
        total = len(all_users)
        all_ids = [int(u.id) for u in all_users]
        friends_count = await fetch_friends_count_for_users(session, all_ids)
        rooms_created, room_seconds, stream_seconds, spectator_seconds, games_played, games_hosted = (
            await aggregate_user_room_stats(session, all_ids)
        )
        sanction_counts = await fetch_sanction_counts_for_users(session, all_ids)
        if sort_key == "last_game_at":
            all_last_game_at = await fetch_users_last_game_at(session, all_ids)
            last_game_at_ts = {
                uid: int(game_dt.timestamp()) if game_dt else 0 for uid, game_dt in all_last_game_at.items()
            }
        else:
            all_last_game_at = {}
            last_game_at_ts = {}

        if sort_key == "username":
            users_sorted = sorted(
                all_users,
                key=lambda u: (
                    admin_username_sort_key(u.username),
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
                        tg_invites_enabled={},
                        friends_count=friends_count,
                        rooms_created=rooms_created,
                        room_seconds=room_seconds,
                        stream_seconds=stream_seconds,
                        games_played=games_played,
                        games_hosted=games_hosted,
                        spectator_seconds=spectator_seconds,
                        sanction_counts=sanction_counts,
                        last_game_at_ts=last_game_at_ts,
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

    ids = [int(u.id) for u in users]
    sanctions_map = await fetch_sanctions_for_users(session, ids)
    now = datetime.now(timezone.utc)
    items: list[ModerationUserOut] = []
    for user in users:
        uid = int(user.id)
        user_sanctions = sanctions_map.get(uid, [])
        timeouts_raw = [row for row in user_sanctions if row.kind == "timeout"]
        bans_raw = [row for row in user_sanctions if row.kind == "ban"]
        suspends_raw = [row for row in user_sanctions if row.kind == SANCTION_SUSPEND]
        active_suspend = next((row for row in suspends_raw if is_sanction_active(row, now)), None)
        items.append(
            ModerationUserOut(
                id=uid,
                username=user.username,
                avatar_name=user.avatar_name,
                registered_at=user.registered_at,
                last_login_at=user.last_login_at,
                last_visit_at=user.last_visit_at,
                last_game_at=last_game_at.get(uid),
                friends_count=friends_count.get(uid, 0),
                rooms_created=rooms_created.get(uid, 0),
                room_minutes=room_seconds.get(uid, 0) // 60,
                stream_minutes=stream_seconds.get(uid, 0) // 60,
                games_played=games_played.get(uid, 0),
                games_hosted=games_hosted.get(uid, 0),
                spectator_minutes=spectator_seconds.get(uid, 0) // 60,
                suspend_active=active_suspend is not None,
                suspend_until=active_suspend.expires_at if active_suspend else None,
                timeouts_count=len(timeouts_raw),
                bans_count=len(bans_raw),
                suspends_count=len(suspends_raw),
                timeouts=[build_admin_sanction_out(row) for row in timeouts_raw],
                bans=[build_admin_sanction_out(row) for row in bans_raw],
                suspends=[build_admin_sanction_out(row) for row in suspends_raw],
            )
        )

    return ModerationUsersOut(total=total, items=items)


@log_route("moderation.users.stats")
@require_roles_deco("moder")
@router.get("/users/{user_id}/stats", response_model=UserStatsOut)
async def moderation_user_stats(user_id: int, season: int | None = None, session: AsyncSession = Depends(get_session)) -> UserStatsOut:
    user = await get_moderation_target_user(session, user_id)
    uid = int(user.id)

    def nonneg_int(raw: object) -> int:
        try:
            return max(0, int(raw))

        except Exception:
            return 0

    try:
        rooms_created, room_seconds, stream_seconds, spectator_seconds = await aggregate_user_room_time_stats(
            session,
            [uid],
            season=season,
        )
        games_in_owned_rooms = await aggregate_user_games_in_owned_rooms_stats(session, [uid], season=season)
        room_minutes = nonneg_int(room_seconds.get(uid, 0)) // 60
        stream_minutes = nonneg_int(stream_seconds.get(uid, 0)) // 60
        spectator_minutes = nonneg_int(spectator_seconds.get(uid, 0)) // 60
        game_stats = await get_user_game_stats_cached(session, uid, season)
    except ValueError as exc:
        detail = str(exc) or "season_invalid"
        if detail not in {"season_invalid", "season_not_found"}:
            detail = "season_invalid"
        raise HTTPException(status_code=422, detail=detail)

    top_player_ids = {int(item.id) for item in (game_stats.top_players or []) if int(item.id) > 0}
    if top_player_ids:
        profiles = await get_user_profiles_cached(session, top_player_ids)
        refreshed_top_players: list[UserTopPlayerOut] = []
        for item in game_stats.top_players:
            profile = profiles.get(int(item.id)) or {}
            username_raw = profile.get("username")
            username_value = str(username_raw) if isinstance(username_raw, str) else item.username
            refreshed_top_players.append(
                UserTopPlayerOut(
                    id=int(item.id),
                    username=username_value,
                    games_together=max(0, int(item.games_together)),
                )
            )
        game_stats = game_stats.model_copy(update={"top_players": refreshed_top_players})

    return UserStatsOut(
        rooms_created=nonneg_int(rooms_created.get(uid, 0)),
        games_in_my_rooms=nonneg_int(games_in_owned_rooms.get(uid, 0)),
        room_minutes=room_minutes,
        stream_minutes=stream_minutes,
        spectator_minutes=spectator_minutes,
        game=game_stats,
    )


@log_route("moderation.users.suspend_add")
@require_roles_deco("moder")
@router.post("/users/{user_id}/suspend", response_model=Ok)
async def moderation_apply_user_suspend(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
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

    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason_required")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=duration_seconds)
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
            "Вы можете проводить игры: после каждой завершенной вами игры срок отстранения от игр будет уменьшаться на 6 часов."
        ),
    )
    session.add(sanction)
    session.add(note)
    await session.commit()
    await session.refresh(note)

    with suppress(Exception):
        redis = get_redis()
        raw_room_id = await redis.get(f"user:{uid}:room")
        room_id = int(raw_room_id) if raw_room_id else 0
        if room_id > 0 and await redis.srem(f"room:{room_id}:ready", str(uid)):
            await sio.emit(
                "state_changed",
                {"user_id": uid, "ready": "0"},
                room=f"room:{room_id}",
                namespace="/room",
            )

    with suppress(Exception):
        await emit_notify(uid, note, kind="sanction")
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
    details += f" duration={duration_label} reason={reason} panel=moderation actor_role={ident['role']}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_suspend_add",
        details=details,
    )

    return Ok()


@log_route("moderation.users.suspend_remove")
@require_roles_deco("moder")
@router.delete("/users/{user_id}/suspend", response_model=Ok)
async def moderation_revoke_user_suspend(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
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
        chat_notice_source="moder" if str(ident["role"]) == "moder" else "admin",
    )

    details = f"Снятие SUSPEND user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" panel=moderation actor_role={ident['role']}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_suspend_remove",
        details=details,
    )

    return Ok()
