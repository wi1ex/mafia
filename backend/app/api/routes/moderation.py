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
from ...models.notif import Notif
from ...models.sanction import UserSanction
from ...models.user import User
from ...schemas.admin import AdminSanctionDurationAdjustIn, AdminSanctionListItemOut, AdminSanctionsOut, AdminSanctionTimedIn, AdminUserNameOut
from ...schemas.common import Identity, Ok
from ...schemas.moderation import ModerationUserOut, ModerationUsersOut
from ...schemas.user import UserStatsOut
from ...realtime.sio import sio
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, require_roles_dep
from ...services.global_chat import emit_global_chat_sanction_issued_notice, emit_global_chat_sanction_removed_notice
from ...services.nickname_history import prepend_nickname_history
from ...services.user_cache import refresh_user_profile_cache
from ..utils import (
    SANCTION_BAN,
    SANCTION_TIMEOUT,
    SANCTION_SUSPEND,
    admin_username_sort_key,
    adjust_active_sanction_duration,
    broadcast_creator_rooms,
    build_user_stats_out,
    close_room_as_staff,
    compute_duration_seconds,
    delete_user_avatar,
    emit_notify,
    emit_sanctions_update,
    fetch_active_sanction,
    fetch_active_sanctions_for_users,
    fetch_sanction_counts_for_users,
    fetch_users_last_game_at,
    force_leave_user_from_rooms,
    format_duration_parts,
    format_duration_seconds_compact,
    get_moderation_target_user,
    moderation_user_sort_metric,
    normalize_pagination,
    normalize_moderation_users_sort,
    maybe_send_sanction_telegram_if_offline,
    revoke_active_suspend,
    sanction_actor_display,
    sanction_finished_at,
    sanction_served_seconds,
    sanction_status,
    fetch_suspend_hosted_workoff_seconds,
    find_user_ids_by_username_search,
)

router = APIRouter(dependencies=[Depends(require_roles_dep("moder"))])


@router.get("/users", response_model=ModerationUsersOut)
@log_route("moderation.users.list")
async def moderation_users_list(page: int = 1, limit: int = 20, username: str | None = None, sort_by: str | None = None, session: AsyncSession = Depends(get_session)) -> ModerationUsersOut:
    limit, page, offset = normalize_pagination(page, limit)
    sort_key = normalize_moderation_users_sort(sort_by)

    filters = [User.deleted_at.is_(None)]
    if username:
        user_ids = await find_user_ids_by_username_search(session, username, include_deleted=False)
        if not user_ids:
            return ModerationUsersOut(total=0, items=[])

        filters.append(User.id.in_(user_ids))

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
        last_game_at = await fetch_users_last_game_at(session, ids)
    else:
        rows = await session.execute(select(User).where(*filters))
        all_users = list(rows.scalars().all())
        total = len(all_users)
        all_ids = [int(u.id) for u in all_users]
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
                    moderation_user_sort_metric(
                        sort_by=sort_key,
                        uid=int(u.id),
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
    sanction_counts = await fetch_sanction_counts_for_users(session, ids)
    active_sanctions = await fetch_active_sanctions_for_users(session, ids)
    items: list[ModerationUserOut] = []
    for user in users:
        uid = int(user.id)
        user_counts = sanction_counts.get(uid, {})
        user_active_sanctions = active_sanctions.get(uid, {})
        active_timeout = user_active_sanctions.get(SANCTION_TIMEOUT)
        active_suspend = user_active_sanctions.get(SANCTION_SUSPEND)
        items.append(
            ModerationUserOut(
                id=uid,
                username=user.username,
                avatar_name=user.avatar_name,
                role=str(user.role),
                registered_at=user.registered_at,
                last_login_at=user.last_login_at,
                last_visit_at=user.last_visit_at,
                last_game_at=last_game_at.get(uid),
                timeout_active=active_timeout is not None,
                timeout_until=active_timeout.expires_at if active_timeout else None,
                suspend_active=active_suspend is not None,
                suspend_until=active_suspend.expires_at if active_suspend else None,
                timeouts_count=int(user_counts.get(SANCTION_TIMEOUT, 0) or 0),
                bans_count=int(user_counts.get(SANCTION_BAN, 0) or 0),
                suspends_count=int(user_counts.get(SANCTION_SUSPEND, 0) or 0),
            )
        )

    return ModerationUsersOut(total=total, items=items)


@router.get("/users/{user_id}/stats", response_model=UserStatsOut)
@log_route("moderation.users.stats")
async def moderation_user_stats(user_id: int, season: int | None = None, session: AsyncSession = Depends(get_session)) -> UserStatsOut:
    uid = int(user_id)
    user = await session.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    return await build_user_stats_out(session, uid, season)


@router.post("/rooms/{room_id}/close", response_model=Ok)
@log_route("moderation.rooms.close")
async def moderation_room_close(room_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    return await close_room_as_staff(
        room_id=room_id,
        ident=ident,
        session=session,
        log_action_name="moderation_room_close",
        details_suffix=f"panel=moderation actor_role={ident['role']}",
    )


@router.post("/users/{user_id}/nickname_reset", response_model=AdminUserNameOut)
@log_route("moderation.users.nickname_reset")
async def moderation_reset_user_nickname(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> AdminUserNameOut:
    user = await get_moderation_target_user(session, user_id)
    uid = int(user.id)
    next_username = f"user_{uid}"
    if str(user.username) == next_username:
        return AdminUserNameOut(id=uid, username=next_username)

    conflict = await session.scalar(select(User.id).where(func.lower(User.username) == next_username.lower(), User.id != uid).limit(1))
    if conflict:
        raise HTTPException(status_code=409, detail="username_taken")

    prev_username = str(user.username)
    user.nickname_history = prepend_nickname_history(user.nickname_history, prev_username, current_username=next_username)
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
        action="moderation_nickname_reset",
        details=f"Nickname reset user_id={uid} from={prev_username} to={next_username} panel=moderation actor_role={ident['role']}",
    )

    return AdminUserNameOut(id=uid, username=next_username)


@router.post("/users/{user_id}/avatar_delete", response_model=Ok)
@log_route("moderation.users.avatar_delete")
async def moderation_delete_user_avatar(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
    uid = int(user.id)
    target_username = str(user.username or f"user{uid}")
    old_avatar_name = await delete_user_avatar(session, uid)

    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="moderation_avatar_delete",
        details=(
            f"Avatar deleted user_id={uid} username={target_username} "
            f"had_avatar={int(bool(old_avatar_name))} panel=moderation actor_role={ident['role']}"
        ),
    )

    return Ok()


@router.get("/sanctions", response_model=AdminSanctionsOut)
@log_route("moderation.sanctions.list")
async def moderation_sanctions_list(page: int = 1, limit: int = 20, username: str | None = None, session: AsyncSession = Depends(get_session)) -> AdminSanctionsOut:
    limit, page, offset = normalize_pagination(page, limit)

    filters = []
    if username:
        user_ids = await find_user_ids_by_username_search(session, username)
        if not user_ids:
            return AdminSanctionsOut(total=0, items=[])

        filters.append(UserSanction.user_id.in_(user_ids))

    total = int(
        await session.scalar(
            select(func.count(UserSanction.id))
            .select_from(UserSanction)
            .outerjoin(User, User.id == UserSanction.user_id)
            .where(*filters)
        ) or 0
    )

    rows = await session.execute(
        select(UserSanction, User.username, User.avatar_name, User.role, User.deleted_at)
        .select_from(UserSanction)
        .outerjoin(User, User.id == UserSanction.user_id)
        .where(*filters)
        .order_by(UserSanction.issued_at.desc(), UserSanction.id.desc())
        .offset(offset)
        .limit(limit)
    )

    now = datetime.now(timezone.utc)
    sanction_rows = rows.all()
    hosted_workoff_seconds = await fetch_suspend_hosted_workoff_seconds(
        session,
        [cast(UserSanction, row) for row, *_rest in sanction_rows],
        now=now,
    )
    items: list[AdminSanctionListItemOut] = []
    for row, target_username, target_avatar_name, target_role, target_deleted_at in sanction_rows:
        sanction = cast(UserSanction, row)
        uid = cast(int, sanction.user_id)
        sid = cast(int, sanction.id)
        issued_by_id = cast(int, sanction.issued_by_id) if sanction.issued_by_id is not None else None
        revoked_by_id = cast(int, sanction.revoked_by_id) if sanction.revoked_by_id is not None else None
        status = sanction_status(sanction, now)
        hosted_workoff = (
            hosted_workoff_seconds.get(sid)
            if sanction.kind == SANCTION_SUSPEND
            else None
        )
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
                avatar_name=cast(str | None, target_avatar_name),
                role=cast(str | None, target_role),
                deleted_at=cast(datetime | None, target_deleted_at),
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
                hosted_workoff_seconds=hosted_workoff,
                reason=sanction.reason or None,
            )
        )

    return AdminSanctionsOut(total=total, items=items)


@router.patch("/sanctions/{sanction_id}/increase", response_model=Ok)
@log_route("moderation.sanctions.increase")
async def moderation_increase_active_sanction_duration(sanction_id: int, payload: AdminSanctionDurationAdjustIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    return await adjust_active_sanction_duration(sanction_id, payload, action="increase", ident=ident, session=session, target_scope="moderation")


@router.patch("/sanctions/{sanction_id}/decrease", response_model=Ok)
@log_route("moderation.sanctions.decrease")
async def moderation_decrease_active_sanction_duration(sanction_id: int, payload: AdminSanctionDurationAdjustIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    return await adjust_active_sanction_duration(sanction_id, payload, action="decrease", ident=ident, session=session, target_scope="moderation")


@router.post("/users/{user_id}/timeout", response_model=Ok)
@log_route("moderation.users.timeout_add")
async def moderation_apply_user_timeout(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_TIMEOUT)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    months = int(payload.months or 0)
    days = int(payload.days or 0)
    hours = int(payload.hours or 0)
    minutes = 0
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
        await emit_notify(uid, note, kind="sanction")
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

    details = f"TIMEOUT user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" duration={duration_label} reason={reason} panel=moderation actor_role={ident['role']}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_timeout_add",
        details=details,
    )

    return Ok()


@router.post("/users/{user_id}/suspend", response_model=Ok)
@log_route("moderation.users.suspend_add")
async def moderation_apply_user_suspend(user_id: int, payload: AdminSanctionTimedIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
    uid = cast(int, user.id)
    active = await fetch_active_sanction(session, uid, SANCTION_SUSPEND)
    if active:
        raise HTTPException(status_code=409, detail="sanction_active")

    months = int(payload.months or 0)
    days = int(payload.days or 0)
    hours = int(payload.hours or 0)
    minutes = 0
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
            "Вы можете проводить игры: после каждой проведенной вами игры срок отстранения от игр будет уменьшаться на 4 часа."
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
    details += f" duration={duration_label} reason={reason} panel=moderation actor_role={ident['role']}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_suspend_add",
        details=details,
    )

    return Ok()


@router.delete("/users/{user_id}/timeout", response_model=Ok)
@log_route("moderation.users.timeout_remove")
async def moderation_revoke_user_timeout(user_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> Ok:
    user = await get_moderation_target_user(session, user_id)
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
        await emit_notify(uid, note, kind="sanction")
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
            source="moder" if str(ident["role"]) == "moder" else "admin",
            remaining_duration_label=remaining_duration_label,
        )

    details = f"Снятие таймаута user_id={uid}"
    if user.username:
        details += f" username={user.username}"
    details += f" panel=moderation actor_role={ident['role']}"
    await log_action(
        session,
        user_id=int(ident["id"]),
        username=ident["username"],
        action="sanction_timeout_remove",
        details=details,
    )

    return Ok()


@router.delete("/users/{user_id}/suspend", response_model=Ok)
@log_route("moderation.users.suspend_remove")
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
