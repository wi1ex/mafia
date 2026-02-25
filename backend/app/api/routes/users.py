from __future__ import annotations
from contextlib import suppress
from typing import cast
from sqlalchemy import select, update, exists, func, literal, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from ..utils import (
    broadcast_creator_rooms,
    SANCTION_TIMEOUT,
    SANCTION_BAN,
    SANCTION_SUSPEND,
    fetch_active_sanctions,
    fetch_sanctions_for_users,
    ensure_profile_changes_allowed,
    set_user_deleted,
    force_logout_user,
    normalize_username,
    is_protected_admin,
    aggregate_user_room_stats,
    safe_int,
    pct,
    role_stats,
)
from ...models.friend import FriendCloseness
from ...models.stats import UserGameStats
from ...models.user import User
from ...core.db import get_session
from ...core.settings import settings
from ...core.logging import log_action
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...services.game_stats import rebuild_user_game_stats
from ...services.text_moderation import enforce_clean_text
from ...schemas.common import Identity, Ok
from ...schemas.user import (
    UserOut,
    UsernameUpdateIn,
    AvatarUploadOut,
    UsernameUpdateOut,
    UserSanctionsOut,
    UserSanctionOut,
    UserUiPrefsIn,
    UserUiPrefsOut,
    PasswordChangeIn,
    UserStatsOut,
    UserGameStatsOut,
    UserBestMoveStatsOut,
    UserTopPlayerOut,
)
from ...security.passwords import hash_password, verify_password
from ...services.minio import put_avatar_async, delete_avatars_async, ALLOWED_CT, MAX_BYTES
from ...services.user_cache import write_user_profile_cache, invalidate_avatar_presign_cache, get_user_profiles_cached

router = APIRouter()


@log_route("users.profile_info")
@rate_limited(lambda ident, **_: f"rl:profile_info:{ident['id']}", limit=10, window_s=1)
@router.get("/profile_info", response_model=UserOut)
async def profile_info(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    user = await db.get(User, int(ident["id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    uid = cast(int, user.id)
    await write_user_profile_cache(uid, username=str(user.username), role=str(user.role), avatar_name=user.avatar_name)
    active = await fetch_active_sanctions(db, uid)
    timeout = active.get(SANCTION_TIMEOUT)
    ban = active.get(SANCTION_BAN)
    suspend = active.get(SANCTION_SUSPEND)

    return UserOut(
        id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        role=user.role,
        registered_at=user.registered_at,
        telegram_verified=bool(user.telegram_id),
        has_password=bool(user.password_hash),
        password_temp=bool(user.password_temp),
        protected_user=is_protected_admin(uid),
        hotkeys_visible=bool(user.hotkeys_visible),
        tg_invites_enabled=bool(user.tg_invites_enabled),
        timeout_until=timeout.expires_at if timeout else None,
        suspend_until=suspend.expires_at if suspend else None,
        ban_active=bool(ban),
    )


@log_route("users.stats")
@rate_limited(lambda ident, **_: f"rl:user_stats:{ident['id']}", limit=10, window_s=1)
@router.get("/stats", response_model=UserStatsOut)
async def user_stats(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserStatsOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    rooms_created, room_seconds, stream_seconds, spectator_seconds, _games_played, _games_hosted = await aggregate_user_room_stats(db, [uid])
    room_minutes = max(0, int(room_seconds.get(uid, 0)) // 60)
    stream_minutes = max(0, int(stream_seconds.get(uid, 0)) // 60)
    spectator_minutes = max(0, int(spectator_seconds.get(uid, 0)) // 60)

    stats_row = await db.get(UserGameStats, uid)
    if not stats_row:
        stats_row = await rebuild_user_game_stats(db, uid)
        await db.commit()

    closeness_rows = await db.execute(
        select(FriendCloseness.user_low, FriendCloseness.user_high, FriendCloseness.games_together)
        .where(
            or_(FriendCloseness.user_low == uid, FriendCloseness.user_high == uid),
            FriendCloseness.games_together > 0,
        )
        .order_by(FriendCloseness.games_together.desc(), FriendCloseness.updated_at.desc(), FriendCloseness.id.desc())
        .limit(5)
    )

    top_ids: list[int] = []
    top_games: dict[int, int] = {}
    for user_low, user_high, games_together in closeness_rows.all():
        lo = int(user_low)
        hi = int(user_high)
        other_id = hi if lo == uid else lo
        if other_id <= 0 or other_id in top_games:
            continue
        top_ids.append(other_id)
        top_games[other_id] = max(0, int(games_together or 0))
        if len(top_ids) >= 5:
            break

    extra_profile_ids: set[int] = set(top_ids)
    profiles = await get_user_profiles_cached(db, extra_profile_ids) if extra_profile_ids else {}

    top_players: list[UserTopPlayerOut] = []
    for other_id in top_ids:
        profile = profiles.get(other_id) or {}
        username_raw = profile.get("username")
        username = str(username_raw) if isinstance(username_raw, str) else None
        top_players.append(
            UserTopPlayerOut(
                id=other_id,
                username=username,
                games_together=top_games.get(other_id, 0),
            )
        )

    games_played = safe_int(getattr(stats_row, "games_decisive", 0))
    games_won = safe_int(getattr(stats_row, "games_won", 0))
    don_games = safe_int(getattr(stats_row, "don_games", 0))
    don_checks_first_night_found = safe_int(getattr(stats_row, "don_checks_first_night_found", 0))
    misses_due_to_me = safe_int(getattr(stats_row, "misses_due_to_me", 0))
    misses_due_to_me_shots = safe_int(getattr(stats_row, "misses_due_to_me_shots", 0))
    vote_leave_day12 = safe_int(getattr(stats_row, "vote_leave_day12", 0))
    foul_removed_count = safe_int(getattr(stats_row, "foul_removed_count", 0))
    vote_for_red_on_black_win_count = safe_int(getattr(stats_row, "vote_for_red_on_black_win_count", 0))
    farewell_total = safe_int(getattr(stats_row, "farewell_total", 0))
    farewell_correct = safe_int(getattr(stats_row, "farewell_correct", 0))

    game_stats = UserGameStatsOut(
        games_played=games_played,
        games_won=games_won,
        winrate_percent=pct(games_won, games_played),
        games_hosted=safe_int(getattr(stats_row, "games_hosted", 0)),
        don_first_night_find_count=don_checks_first_night_found,
        don_first_night_find_percent=pct(don_checks_first_night_found, don_games),
        misses_due_to_me=misses_due_to_me,
        misses_due_to_me_shots=misses_due_to_me_shots,
        misses_due_to_me_percent=pct(misses_due_to_me, misses_due_to_me_shots),
        vote_leave_day12_count=vote_leave_day12,
        vote_leave_day12_percent=pct(vote_leave_day12, games_played),
        foul_removed_count=foul_removed_count,
        foul_removed_percent=pct(foul_removed_count, games_played),
        vote_for_red_on_black_win_count=vote_for_red_on_black_win_count,
        farewell_total=farewell_total,
        farewell_success_percent=pct(farewell_correct, farewell_total),
        best_win_streak=safe_int(getattr(stats_row, "best_win_streak", 0)),
        best_loss_streak=safe_int(getattr(stats_row, "best_loss_streak", 0)),
        role_citizen=role_stats(getattr(stats_row, "citizen_games", 0), getattr(stats_row, "citizen_wins", 0)),
        role_sheriff=role_stats(getattr(stats_row, "sheriff_games", 0), getattr(stats_row, "sheriff_wins", 0)),
        role_don=role_stats(getattr(stats_row, "don_games", 0), getattr(stats_row, "don_wins", 0)),
        role_mafia=role_stats(getattr(stats_row, "mafia_games", 0), getattr(stats_row, "mafia_wins", 0)),
        best_move=UserBestMoveStatsOut(
            first_killed_total=safe_int(getattr(stats_row, "first_killed_best_move_total", 0)),
            marks_black_0=safe_int(getattr(stats_row, "best_move_black_0", 0)),
            marks_black_1=safe_int(getattr(stats_row, "best_move_black_1", 0)),
            marks_black_2=safe_int(getattr(stats_row, "best_move_black_2", 0)),
            marks_black_3=safe_int(getattr(stats_row, "best_move_black_3", 0)),
        ),
        top_players=top_players,
    )

    return UserStatsOut(
        rooms_created=max(0, safe_int(rooms_created.get(uid, 0))),
        room_minutes=room_minutes,
        stream_minutes=stream_minutes,
        spectator_minutes=spectator_minutes,
        game=game_stats,
    )


@log_route("users.sanctions_history")
@rate_limited(lambda ident, **_: f"rl:sanctions_history:{ident['id']}", limit=10, window_s=1)
@router.get("/sanctions", response_model=UserSanctionsOut)
async def sanctions_history(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserSanctionsOut:
    user = await db.get(User, int(ident["id"]))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    uid = cast(int, user.id)
    sanctions_map = await fetch_sanctions_for_users(db, [uid])
    rows = sanctions_map.get(uid, [])
    items = [
        UserSanctionOut(
            id=cast(int, row.id),
            kind=str(row.kind),
            reason=row.reason or None,
            issued_at=row.issued_at,
            issued_by_id=cast(int, row.issued_by_id) if row.issued_by_id is not None else None,
            issued_by_name=row.issued_by_name,
            duration_seconds=row.duration_seconds,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            revoked_by_id=cast(int, row.revoked_by_id) if row.revoked_by_id is not None else None,
            revoked_by_name=row.revoked_by_name,
        )
        for row in rows
    ]

    return UserSanctionsOut(items=items)


@log_route("users.update_username")
@rate_limited(lambda ident, **_: f"rl:update_username:{ident['id']}", limit=1, window_s=1)
@router.patch("/username", response_model=UsernameUpdateOut)
async def update_username(payload: UsernameUpdateIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UsernameUpdateOut:
    uid = int(ident["id"])
    new = normalize_username(payload.username)
    if new.lower().startswith(("deleted_", "user_")):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_username_format")

    enforce_clean_text(field="username", label="Никнейм", value=new)

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="protected_user")

    await ensure_profile_changes_allowed(db, uid)

    if user.username == new:
        return UsernameUpdateOut(username=user.username)

    exists_case_ins = await db.scalar(select(exists().where(and_(func.lower(User.username) == func.lower(literal(new)), User.id != uid))))
    if exists_case_ins:
        raise HTTPException(status_code=409, detail="username_taken")

    old_username = user.username
    await db.execute(update(User).where(User.id == uid).values(username=new))
    await db.commit()
    await write_user_profile_cache(uid, username=new, role=str(user.role), avatar_name=user.avatar_name)

    await log_action(
        db,
        user_id=uid,
        username=new,
        action="username_updated",
        details=f"Изменение никнейма: {old_username} -> {new}",
    )

    await broadcast_creator_rooms(uid, update_name=new)
    return UsernameUpdateOut(username=new)


@log_route("users.update_ui_prefs")
@rate_limited(lambda ident, **_: f"rl:update_ui_prefs:{ident['id']}", limit=10, window_s=1)
@router.patch("/ui_prefs", response_model=UserUiPrefsOut)
async def update_ui_prefs(payload: UserUiPrefsIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserUiPrefsOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    old_hotkeys_visible = bool(user.hotkeys_visible)
    old_tg_invites_enabled = bool(user.tg_invites_enabled)

    if payload.hotkeys_visible is not None:
        user.hotkeys_visible = bool(payload.hotkeys_visible)
    if payload.tg_invites_enabled is not None:
        user.tg_invites_enabled = bool(payload.tg_invites_enabled)

    new_hotkeys_visible = bool(user.hotkeys_visible)
    new_tg_invites_enabled = bool(user.tg_invites_enabled)
    await db.commit()

    changes: list[str] = []
    if old_hotkeys_visible != new_hotkeys_visible:
        changes.append(f"hotkeys_visible: {int(old_hotkeys_visible)} -> {int(new_hotkeys_visible)}")
    if old_tg_invites_enabled != new_tg_invites_enabled:
        changes.append(f"tg_invites_enabled: {int(old_tg_invites_enabled)} -> {int(new_tg_invites_enabled)}")

    if changes:
        await log_action(
            db,
            user_id=uid,
            username=ident["username"],
            action="ui_prefs_updated",
            details="UI prefs updated: " + "; ".join(changes),
        )

    return UserUiPrefsOut(
        hotkeys_visible=new_hotkeys_visible,
        tg_invites_enabled=new_tg_invites_enabled,
    )


@log_route("users.change_password")
@rate_limited(lambda ident, **_: f"rl:change_password:{ident['id']}", limit=1, window_s=1)
@router.patch("/password", response_model=Ok)
async def change_password(payload: PasswordChangeIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    if user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password_not_set")

    password_hash = str(user.password_hash)
    if not verify_password(payload.current_password, password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    user.password_hash = hash_password(payload.new_password)
    user.password_temp = False
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="password_changed",
        details=f"Смена пароля user_id={uid} username={ident['username']}",
    )

    return Ok()


@log_route("users.unverify_telegram")
@rate_limited(lambda ident, **_: f"rl:unverify_telegram:{ident['id']}", limit=1, window_s=1)
@router.post("/unverify", response_model=Ok)
async def unverify_telegram(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    prev_tg = user.telegram_id
    if prev_tg is None:
        return Ok()

    user.telegram_id = None
    await db.commit()

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="telegram_unverified_self",
        details=f"Пользователь отвязал Telegram: user_id={uid} username={ident['username']} tg_id={prev_tg}",
    )

    return Ok()


@log_route("users.upload_avatar")
@rate_limited(lambda ident, **_: f"rl:upload_avatar:{ident['id']}", limit=1, window_s=1)
@router.post("/avatar", response_model=AvatarUploadOut)
async def upload_avatar(file: UploadFile = File(...), ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> AvatarUploadOut:
    uid = int(ident["id"])
    await ensure_profile_changes_allowed(db, uid)

    row = await db.execute(select(User.username, User.avatar_name, User.role).where(User.id == uid))
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    db_username = str(rec[0])
    old_avatar_name = cast(str | None, rec[1])
    db_role = str(rec[2])
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=415, detail="unsupported_media_type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty_file")

    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    name = await put_avatar_async(uid, data, ct)
    if not name:
        raise HTTPException(status_code=422, detail="bad_image")

    await db.execute(update(User).where(User.id == uid).values(avatar_name=name))
    await db.commit()
    await write_user_profile_cache(uid, username=db_username, role=db_role, avatar_name=name)
    await invalidate_avatar_presign_cache(old_avatar_name)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_updated",
        details="Изменение аватара",
    )

    await broadcast_creator_rooms(uid, avatar="set", avatar_name=name)
    return AvatarUploadOut(avatar_name=name)


@log_route("users.delete_avatar")
@rate_limited(lambda ident, **_: f"rl:delete_avatar:{ident['id']}", limit=1, window_s=1)
@router.delete("/avatar", response_model=Ok)
async def delete_avatar(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    await ensure_profile_changes_allowed(db, uid)

    row = await db.execute(select(User.username, User.avatar_name, User.role).where(User.id == uid))
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    db_username = str(rec[0])
    old_avatar_name = cast(str | None, rec[1])
    db_role = str(rec[2])

    await db.execute(update(User).where(User.id == uid).values(avatar_name=None))
    await db.commit()
    await write_user_profile_cache(uid, username=db_username, role=db_role, avatar_name=None)
    await invalidate_avatar_presign_cache(old_avatar_name)

    with suppress(Exception):
        await delete_avatars_async(uid)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_deleted",
        details="Удаление аватара",
    )

    await broadcast_creator_rooms(uid, avatar="delete")
    return Ok()


@log_route("users.delete_account")
@rate_limited(lambda ident, **_: f"rl:delete_account:{ident['id']}", limit=1, window_s=5)
@router.delete("/account", response_model=Ok)
async def delete_account(resp: Response, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="protected_user")

    await set_user_deleted(db, uid, deleted=True)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="account_deleted",
        details=f"Удаление аккаунта user_id={uid} username={ident['username']}",
    )

    await force_logout_user(uid)
    resp.delete_cookie("rt", path="/api", domain=settings.DOMAIN, samesite="strict", secure=True)
    return Ok()
