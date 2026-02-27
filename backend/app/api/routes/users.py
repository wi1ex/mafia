from __future__ import annotations
from contextlib import suppress
from typing import cast, Literal
from sqlalchemy import select, update, exists, func, literal, and_
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
    safe_int,
    non_empty_str,
    normalize_game_result,
    fetch_games_history_page,
    aggregate_user_room_time_stats,
)
from ...models.game import Game
from ...models.user import User
from ...core.db import get_session
from ...core.settings import settings
from ...core.logging import log_action
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...services.user_stats import get_user_game_stats_cached
from ...services.text_moderation import enforce_clean_text
from ...schemas.common import Identity, Ok
from ...schemas.user import (
    UserOut,
    UsernameUpdateIn,
    AvatarUploadOut,
    UsernameUpdateOut,
    UserSanctionsOut,
    UserSanctionOut,
    UserGamesHistoryOut,
    GameHistoryItemOut,
    GameHistoryHostOut,
    GameHistoryFarewellItemOut,
    GameHistoryNightCheckItemOut,
    GameHistorySlotOut,
    UserUiPrefsIn,
    UserUiPrefsOut,
    PasswordChangeIn,
    UserStatsOut,
    UserTopPlayerOut,
)
from ...security.passwords import hash_password, verify_password
from ...services.minio import put_avatar_async, delete_avatars_async, ALLOWED_CT, MAX_BYTES
from ...services.user_cache import write_user_profile_cache, invalidate_avatar_presign_cache, get_user_profiles_cached

router = APIRouter()

GAME_HISTORY_PER_PAGE = 20
PERSONAL_GAME_HISTORY_PER_PAGE = 10


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
async def user_stats(season: int | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserStatsOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    try:
        rooms_created, room_seconds, stream_seconds, spectator_seconds = await aggregate_user_room_time_stats(db, [uid], season=season)
        room_minutes = max(0, int(room_seconds.get(uid, 0)) // 60)
        stream_minutes = max(0, int(stream_seconds.get(uid, 0)) // 60)
        spectator_minutes = max(0, int(spectator_seconds.get(uid, 0)) // 60)
        game_stats = await get_user_game_stats_cached(db, uid, season)
    except ValueError as exc:
        detail = str(exc) or "season_invalid"
        if detail not in {"season_invalid", "season_not_found"}:
            detail = "season_invalid"
        raise HTTPException(status_code=422, detail=detail)

    top_player_ids = {int(item.id) for item in (game_stats.top_players or []) if int(item.id) > 0}
    if top_player_ids:
        profiles = await get_user_profiles_cached(db, top_player_ids)
        refreshed_top_players: list[UserTopPlayerOut] = []
        for item in game_stats.top_players:
            profile = profiles.get(int(item.id)) or {}
            username_raw = profile.get("username")
            username = str(username_raw) if isinstance(username_raw, str) else item.username
            refreshed_top_players.append(
                UserTopPlayerOut(
                    id=int(item.id),
                    username=username,
                    games_together=max(0, int(item.games_together)),
                )
            )
        game_stats = game_stats.model_copy(update={"top_players": refreshed_top_players})

    return UserStatsOut(
        rooms_created=max(0, safe_int(rooms_created.get(uid, 0))),
        room_minutes=room_minutes,
        stream_minutes=stream_minutes,
        spectator_minutes=spectator_minutes,
        game=game_stats,
    )


@log_route("users.games_history")
@rate_limited(lambda ident, **_: f"rl:games_history:{ident['id']}", limit=10, window_s=1)
@router.get("/games/history", response_model=UserGamesHistoryOut)
async def games_history(page: int = 1, _ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserGamesHistoryOut:
    return await fetch_games_history_page(db, page=page, per_page=GAME_HISTORY_PER_PAGE)


@log_route("users.games_history_personal")
@rate_limited(lambda ident, **_: f"rl:games_history_personal:{ident['id']}", limit=10, window_s=1)
@router.get("/games/history/personal", response_model=UserGamesHistoryOut)
async def games_history_personal(page: int = 1, role: Literal["citizen", "mafia", "don", "sheriff"] | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserGamesHistoryOut:
    uid = safe_int((ident or {}).get("id"))
    return await fetch_games_history_page(
        db,
        page=page,
        player_uid=uid,
        player_role=role,
        per_page=PERSONAL_GAME_HISTORY_PER_PAGE,
    )


@log_route("users.game_history_details")
@rate_limited(lambda ident, game_id=None, **_: f"rl:game_history_details:{ident['id']}:{game_id}", limit=10, window_s=1)
@router.get("/games/history/{game_id}", response_model=GameHistoryItemOut)
async def game_history_details(game_id: int, _ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> GameHistoryItemOut:
    GAME_HISTORY_MAX_SLOT = 10
    GAME_HISTORY_ROLES = {"citizen", "mafia", "don", "sheriff"}
    GAME_HISTORY_LEAVE_REASONS = {"vote", "foul", "suicide", "night"}
    GAME_HISTORY_FAREWELL_VERDICTS = {"citizen", "mafia"}

    gid_req = safe_int(game_id)
    if gid_req <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    row = await db.execute(
        select(
            Game.id,
            Game.head_id,
            Game.result,
            Game.black_alive_at_finish,
            Game.started_at,
            Game.finished_at,
            Game.roles,
            Game.seats,
            Game.points,
            Game.mmr,
            Game.actions,
        )
        .where(Game.id == gid_req)
        .limit(1)
    )
    rec = row.first()
    if not rec:
        raise HTTPException(status_code=404, detail="game_not_found")

    game_id_raw, head_id, result_raw, black_alive_raw, started_at, finished_at, roles_raw, seats_raw, points_raw, mmr_raw, actions_raw = rec
    gid = safe_int(game_id_raw)
    if gid <= 0:
        raise HTTPException(status_code=404, detail="game_not_found")

    head_uid = safe_int(head_id)
    head_auto = head_uid <= 0

    roles_map = roles_raw if isinstance(roles_raw, dict) else {}
    points_map = points_raw if isinstance(points_raw, dict) else {}
    mmr_map = mmr_raw if isinstance(mmr_raw, dict) else {}

    slot_map: dict[int, int] = {}
    if isinstance(seats_raw, dict):
        for raw_uid, raw_slot in seats_raw.items():
            uid_i = safe_int(raw_uid)
            slot_i = safe_int(raw_slot)
            if uid_i <= 0:
                continue
            if slot_i < 1 or slot_i > GAME_HISTORY_MAX_SLOT:
                continue
            if slot_i in slot_map:
                continue
            slot_map[slot_i] = uid_i

    user_ids: set[int] = set(slot_map.values())
    if head_uid > 0:
        user_ids.add(head_uid)
    profiles = await get_user_profiles_cached(db, user_ids) if user_ids else {}

    head_profile = profiles.get(head_uid) if head_uid > 0 else None
    head_username = non_empty_str((head_profile or {}).get("username"))
    if head_username is None and head_uid > 0:
        head_username = f"user{head_uid}"
    head_avatar_name = non_empty_str((head_profile or {}).get("avatar_name"))

    uid_to_slot = {player_uid: seat_num for seat_num, player_uid in slot_map.items()}
    leave_map: dict[int, tuple[int, str, list[int]]] = {}
    best_move_map: dict[int, list[int]] = {}
    farewell_map: dict[int, list[tuple[int, str]]] = {}
    night_check_map: dict[int, list[tuple[int, str]]] = {}
    if isinstance(actions_raw, list):
        for action in actions_raw:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").strip().lower()
            if action_type == "death":
                target_uid = safe_int(action.get("target_id"))
                if target_uid <= 0:
                    continue
                leave_day = safe_int(action.get("day"))
                if leave_day <= 0:
                    continue
                leave_reason = str(action.get("reason") or "").strip().lower()
                if leave_reason not in GAME_HISTORY_LEAVE_REASONS:
                    continue
                if target_uid in leave_map:
                    continue
                voted_by_user_ids: list[int] = []
                raw_by = action.get("by")
                if isinstance(raw_by, list):
                    seen_by: set[int] = set()
                    for raw_voter_uid in raw_by:
                        voter_uid = safe_int(raw_voter_uid)
                        if voter_uid <= 0 or voter_uid in seen_by:
                            continue
                        seen_by.add(voter_uid)
                        voted_by_user_ids.append(voter_uid)
                leave_map[target_uid] = (leave_day, leave_reason, voted_by_user_ids)
                continue

            if action_type == "best_move":
                actor_uid = safe_int(action.get("actor_id"))
                if actor_uid <= 0 or actor_uid in best_move_map:
                    continue
                raw_targets = action.get("targets")
                if not isinstance(raw_targets, list):
                    continue
                targets: list[int] = []
                seen_targets: set[int] = set()
                for raw_target_uid in raw_targets:
                    target_uid = safe_int(raw_target_uid)
                    if target_uid <= 0 or target_uid in seen_targets:
                        continue
                    seen_targets.add(target_uid)
                    targets.append(target_uid)
                    if len(targets) >= 3:
                        break
                if targets:
                    best_move_map[actor_uid] = targets
                continue

            if action_type != "farewell":
                if action_type == "night_check":
                    actor_uid = safe_int(action.get("actor_id"))
                    target_uid = safe_int(action.get("target_id"))
                    if actor_uid <= 0 or target_uid <= 0:
                        continue
                    checker_role = str(action.get("checker_role") or "").strip().lower()
                    if checker_role not in ("don", "sheriff"):
                        checker_role = str(roles_map.get(str(actor_uid)) or "").strip().lower()
                    if checker_role not in ("don", "sheriff"):
                        continue
                    target_role = str(action.get("target_role") or "").strip().lower()
                    if not target_role:
                        target_role = str(roles_map.get(str(target_uid)) or "").strip().lower()
                    if checker_role == "sheriff":
                        verdict = "mafia" if target_role in ("mafia", "don") else "citizen"
                    else:
                        verdict = "sheriff" if target_role == "sheriff" else "citizen"
                    bucket = night_check_map.setdefault(actor_uid, [])
                    if any(prev_target_uid == target_uid for prev_target_uid, _ in bucket):
                        continue
                    bucket.append((target_uid, verdict))
                continue
            actor_uid = safe_int(action.get("actor_id"))
            if actor_uid <= 0 or actor_uid in farewell_map:
                continue
            wills_raw = action.get("wills")
            if not isinstance(wills_raw, dict):
                continue
            picks: list[tuple[int, str]] = []
            seen_targets: set[int] = set()
            for raw_target_uid, raw_verdict in wills_raw.items():
                target_uid = safe_int(raw_target_uid)
                if target_uid <= 0 or target_uid in seen_targets:
                    continue
                verdict = str(raw_verdict or "").strip().lower()
                if verdict not in GAME_HISTORY_FAREWELL_VERDICTS:
                    continue
                seen_targets.add(target_uid)
                picks.append((target_uid, verdict))
            if picks:
                farewell_map[actor_uid] = picks

    slots: list[GameHistorySlotOut] = []
    for slot in range(1, GAME_HISTORY_MAX_SLOT + 1):
        slot_uid = slot_map.get(slot)
        profile = profiles.get(slot_uid) if slot_uid else None
        username = non_empty_str((profile or {}).get("username"))
        if username is None and slot_uid:
            username = f"user{slot_uid}"
        avatar_name = non_empty_str((profile or {}).get("avatar_name"))
        role_value = None
        points = 0
        mmr = 0
        leave_day_value = None
        leave_reason_value = None
        voted_by_slots: list[int] = []
        best_move_slots: list[int] = []
        farewell_items: list[GameHistoryFarewellItemOut] = []
        night_check_items: list[GameHistoryNightCheckItemOut] = []
        if slot_uid:
            raw_role = str(roles_map.get(str(slot_uid)) or "").strip().lower()
            if raw_role in GAME_HISTORY_ROLES:
                role_value = raw_role
            points = safe_int(points_map.get(str(slot_uid), 0))
            mmr = safe_int(mmr_map.get(str(slot_uid), 0))
            leave_data = leave_map.get(slot_uid)
            if leave_data:
                leave_day_value = leave_data[0]
                leave_reason_value = leave_data[1]
                if leave_reason_value == "vote":
                    for voter_uid in leave_data[2]:
                        voter_slot = safe_int(uid_to_slot.get(voter_uid))
                        if voter_slot <= 0 or voter_slot in voted_by_slots:
                            continue
                        voted_by_slots.append(voter_slot)
                    voted_by_slots.sort()
            best_move_targets = best_move_map.get(slot_uid, [])
            if best_move_targets:
                for target_uid in best_move_targets:
                    target_slot = safe_int(uid_to_slot.get(target_uid))
                    if target_slot <= 0 or target_slot in best_move_slots:
                        continue
                    best_move_slots.append(target_slot)
                best_move_slots.sort()
            farewell_picks = farewell_map.get(slot_uid, [])
            if farewell_picks:
                normalized_picks: list[tuple[int, str]] = []
                seen_farewell_slots: set[int] = set()
                for target_uid, verdict in farewell_picks:
                    target_slot = safe_int(uid_to_slot.get(target_uid))
                    if target_slot <= 0 or target_slot in seen_farewell_slots:
                        continue
                    seen_farewell_slots.add(target_slot)
                    normalized_picks.append((target_slot, verdict))
                normalized_picks.sort(key=lambda item: item[0])
                farewell_items = [
                    GameHistoryFarewellItemOut(slot=target_slot, verdict=verdict)
                    for target_slot, verdict in normalized_picks
                ]
            night_checks = night_check_map.get(slot_uid, [])
            if night_checks:
                normalized_checks: list[tuple[int, str]] = []
                seen_check_slots: set[int] = set()
                for target_uid, verdict in night_checks:
                    target_slot = safe_int(uid_to_slot.get(target_uid))
                    if target_slot <= 0 or target_slot in seen_check_slots:
                        continue
                    seen_check_slots.add(target_slot)
                    normalized_checks.append((target_slot, verdict))
                night_check_items = [
                    GameHistoryNightCheckItemOut(slot=target_slot, verdict=verdict)
                    for target_slot, verdict in normalized_checks
                ]
        slots.append(
            GameHistorySlotOut(
                slot=slot,
                user_id=slot_uid,
                username=username,
                avatar_name=avatar_name,
                role=role_value,
                points=points,
                mmr=mmr,
                leave_day=leave_day_value,
                leave_reason=leave_reason_value,
                voted_by_slots=voted_by_slots,
                best_move_slots=best_move_slots,
                farewell=farewell_items,
                night_checks=night_check_items,
            )
        )

    try:
        duration_seconds = max(0, int((finished_at - started_at).total_seconds()))
    except Exception:
        duration_seconds = 0

    return GameHistoryItemOut(
        id=gid,
        number=gid,
        head=GameHistoryHostOut(
            id=head_uid if not head_auto else None,
            username=head_username,
            avatar_name=head_avatar_name,
            auto=head_auto,
        ),
        result=normalize_game_result(result_raw),
        black_alive_at_finish=max(0, safe_int(black_alive_raw)),
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        slots=slots,
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
