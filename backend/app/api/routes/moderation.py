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
from ...schemas.admin import AdminSanctionListItemOut, AdminSanctionsOut, AdminSanctionTimedIn
from ...schemas.common import Identity, Ok
from ...schemas.moderation import ModerationUserOut, ModerationUsersOut
from ...realtime.sio import sio
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, require_roles_dep
from ...services.global_chat import emit_global_chat_sanction_issued_notice, emit_global_chat_sanction_removed_notice
from ..utils import (
    SANCTION_TIMEOUT,
    SANCTION_SUSPEND,
    admin_username_sort_key,
    build_admin_sanction_out,
    compute_duration_seconds,
    emit_notify,
    emit_sanctions_update,
    fetch_active_sanction,
    fetch_sanction_counts_for_users,
    fetch_sanctions_for_users,
    fetch_users_last_game_at,
    force_leave_user_from_rooms,
    format_duration_parts,
    format_duration_seconds_compact,
    get_moderation_target_user,
    is_sanction_active,
    moderation_user_sort_metric,
    normalize_pagination,
    normalize_moderation_users_sort,
    maybe_send_sanction_telegram_if_offline,
    revoke_active_suspend,
    sanction_actor_display,
    sanction_finished_at,
    sanction_served_seconds,
    sanction_status,
)

router = APIRouter(dependencies=[Depends(require_roles_dep("moder"))])


@router.get("/users", response_model=ModerationUsersOut)
@log_route("moderation.users.list")
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
    sanctions_map = await fetch_sanctions_for_users(session, ids)
    now = datetime.now(timezone.utc)
    items: list[ModerationUserOut] = []
    for user in users:
        uid = int(user.id)
        user_sanctions = sanctions_map.get(uid, [])
        timeouts_raw = [row for row in user_sanctions if row.kind == "timeout"]
        bans_raw = [row for row in user_sanctions if row.kind == "ban"]
        suspends_raw = [row for row in user_sanctions if row.kind == SANCTION_SUSPEND]
        active_timeout = next((row for row in timeouts_raw if is_sanction_active(row, now)), None)
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
                timeout_active=active_timeout is not None,
                timeout_until=active_timeout.expires_at if active_timeout else None,
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

@router.get("/sanctions", response_model=AdminSanctionsOut)
@log_route("moderation.sanctions.list")
async def moderation_sanctions_list(page: int = 1, limit: int = 20, username: str | None = None, session: AsyncSession = Depends(get_session)) -> AdminSanctionsOut:
    limit, page, offset = normalize_pagination(page, limit)

    filters = [User.role == ROLE_USER]
    if username:
        needle = username.lower()
        filters.append(func.lower(User.username).contains(needle, autoescape=True))

    total = int(
        await session.scalar(
            select(func.count(UserSanction.id))
            .select_from(UserSanction)
            .join(User, User.id == UserSanction.user_id)
            .where(*filters)
        ) or 0
    )

    rows = await session.execute(
        select(UserSanction, User.username)
        .select_from(UserSanction)
        .join(User, User.id == UserSanction.user_id)
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
            "Вы можете проводить игры: после каждой проведенной вами игры срок отстранения от игр будет уменьшаться на 6 часов."
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
