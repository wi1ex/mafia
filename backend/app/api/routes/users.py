from __future__ import annotations
from contextlib import suppress
from typing import cast, Literal
from sqlalchemy import select, update, exists, func, literal, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response, Request
from ..utils import (
    broadcast_creator_rooms,
    fetch_active_sanctions,
    fetch_sanctions_for_users,
    pick_active_sanction_kind,
    ensure_profile_changes_allowed,
    set_user_deleted,
    force_logout_user,
    normalize_chat_mention_query,
    normalize_password,
    normalize_username,
    is_protected_admin,
    delete_user_avatar,
    safe_int,
    non_empty_str,
    contact_request_rate_key,
    normalize_game_result,
    fetch_games_history_page,
    build_user_stats_out,
    build_user_out_payload,
    emit_auth_profile_sync,
    emit_room_profile_theme_sync,
    ensure_verification_allowed,
    fetch_effective_online_user_ids,
    fetch_online_user_ids,
    fetch_friends_count_for_users,
    build_admin_mini_profile_friends,
    build_user_mini_profile_nomination_stats_out,
    friend_status_for,
)
from ...models.game import Game
from ...models.user import User
from ...core.db import get_session
from ...core.roles import ROLE_MODER, normalize_user_role
from ...core.settings import settings
from ...core.clients import get_redis
from ...core.logging import log_action
from ...security.auth_tokens import get_identity, get_identity_optional
from ...security.decorators import log_route, rate_limited
from ...services.text_moderation import enforce_clean_text
from ...services.telegram import send_text_message
from ...schemas.common import Identity, Ok
from ...schemas.user import (
    UserOut,
    UsernameUpdateIn,
    AvatarUploadOut,
    ChatImagePresignIn,
    ChatImagePresignOut,
    ChatImageUploadOut,
    ChatMentionSearchOut,
    ChatMentionUserOut,
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
    SupportLinkClickIn,
    ContactRequestIn,
    UserProfileThemeIn,
    UserProfileThemeOut,
    PasswordChangeIn,
    UserStatsOut,
    UserMiniProfileOut,
    UserMiniProfileSanctionOut,
    UserMiniProfileNominationStatsOut,
    UserNicknameHistoryOut,
)
from ...security.passwords import hash_password, verify_password
from ...services.global_chat import global_chat_send_error, resolve_global_chat_permissions
from ...services.global_chat import (
    emit_global_chat_messages_refresh,
    emit_global_chat_permissions_updated,
    ensure_global_chat_image_owned_by_user,
    is_global_chat_image_referenced,
    normalize_global_chat_image_object_key,
)
from ...services.minio import (
    put_avatar_async,
    build_chat_image_object_name,
    delete_object_async,
    put_chat_image_async,
    build_chat_image_post_upload_async,
    ALLOWED_CT,
    AVATAR_ALLOWED_CT,
    MAX_BYTES,
    CHAT_IMAGE_MAX_BYTES,
)
from ...services.profile_theme import (
    ensure_profile_theme_defaults,
    normalize_profile_theme_color,
    normalize_profile_theme_icon,
    resolve_profile_theme_state,
    upsert_profile_theme_icon_preference,
    upsert_profile_theme_preference,
)
from ...services.nickname_history import (
    build_nickname_history_out,
    prepend_nickname_history,
    serialize_nickname_history,
)
from ...services.user_cache import (
    refresh_user_profile_cache,
    write_user_profile_cache,
    invalidate_avatar_presign_cache,
    get_user_profiles_cached,
)

router = APIRouter()

GAME_HISTORY_PER_PAGE = 20
PERSONAL_GAME_HISTORY_PER_PAGE = 10
CHAT_MENTION_LIMIT_DEFAULT = 8
CHAT_MENTION_LIMIT_MAX = 10
CHAT_MENTION_SEARCH_RATE_LIMIT = 100
CHAT_MENTION_SEARCH_RATE_WINDOW_S = 10
CONTACT_REQUEST_TELEGRAM_ID = 59404714


@router.get("/profile_info", response_model=UserOut)
@log_route("users.profile_info")
@rate_limited(lambda ident, **_: f"rl:profile_info:{ident['id']}", limit=10, window_s=1)
async def profile_info(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserOut:
    return await build_user_out_payload(db, user_id=int(ident["id"]), role=str(ident["role"]))


@router.get("/stats", response_model=UserStatsOut)
@log_route("users.stats")
@rate_limited(lambda ident, **_: f"rl:user_stats:{ident['id']}", limit=10, window_s=1)
async def user_stats(season: int | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserStatsOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return await build_user_stats_out(db, uid, season)


@router.get("/{user_id}/stats", response_model=UserStatsOut)
@log_route("users.public_stats")
@rate_limited(lambda ident, user_id, **_: f"rl:user_public_stats:{ident['id']}:{user_id}", limit=10, window_s=1)
async def public_user_stats(user_id: int, season: int | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserStatsOut:
    viewer_id = int(ident["id"])
    viewer_role = str(ident["role"] or "").strip().lower()
    uid = int(user_id)
    if uid <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    user = await db.get(User, uid)
    if not user or user.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if uid != viewer_id and viewer_role not in {"admin", "moder"}:
        friendship_status = await friend_status_for(db, viewer_id, uid)
        if friendship_status != "friends":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="friends_only")

    return await build_user_stats_out(db, uid, season)


@router.get("/{user_id}/mini_profile", response_model=UserMiniProfileOut)
@log_route("users.mini_profile")
@rate_limited(lambda ident, user_id, **_: f"rl:user_mini_profile:{ident['id']}:{user_id}", limit=10, window_s=1)
async def mini_profile(user_id: int, allow_deleted: bool = False, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserMiniProfileOut:
    viewer_id = int(ident["id"])
    await ensure_verification_allowed(db, viewer_id)
    viewer_role = str(ident["role"] or "").strip().lower()
    is_staff_viewer = viewer_role in {"admin", "moder"}
    uid = int(user_id)
    if uid <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    target_role = str(user.role or "user").strip().lower()
    if target_role == "admin" and viewer_role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if user.deleted_at and not (allow_deleted and is_staff_viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    defaults_changed = await ensure_profile_theme_defaults(db, uid)
    if defaults_changed:
        await db.commit()
    theme_state = await resolve_profile_theme_state(db, uid)
    last_game_id: int | None = None
    last_game_at = None
    last_game_row = await db.execute(
        select(Game.id, Game.finished_at)
        .where(Game.roles.has_key(str(uid)))
        .order_by(Game.finished_at.desc(), Game.id.desc())
        .limit(1)
    )
    last_game_rec = last_game_row.first()
    if last_game_rec:
        last_game_id = int(last_game_rec[0])
        last_game_at = last_game_rec[1]

    friends_count = (await fetch_friends_count_for_users(db, [uid])).get(uid, 0)
    admin_friends = (
        await build_admin_mini_profile_friends(db, uid)
        if viewer_role == "admin"
        else None
    )
    active_sanctions = await fetch_active_sanctions(db, uid)
    active_sanction_kind = pick_active_sanction_kind(active_sanctions)
    active_sanction = None
    if active_sanction_kind:
        active_sanction_row = active_sanctions.get(active_sanction_kind)
        if active_sanction_row is not None:
            active_sanction = UserMiniProfileSanctionOut(
                kind=active_sanction_kind,
                expires_at=active_sanction_row.expires_at,
            )

    nomination_stats: UserMiniProfileNominationStatsOut | None = None
    with suppress(Exception):
        nomination_stats = await build_user_mini_profile_nomination_stats_out(db, uid)

    friend_status = await friend_status_for(db, viewer_id, uid)
    viewer_username = str(ident.get("username") or f"user{viewer_id}")
    target_username = user.username or f"user{uid}"

    online = False
    with suppress(Exception):
        r = get_redis()
        base_online_ids = set(await fetch_online_user_ids(r))
        online_ids = await fetch_effective_online_user_ids(r, [uid], base_online_ids=base_online_ids)
        online = uid in online_ids

    if viewer_role != "admin" and uid != viewer_id:
        await log_action(
            db,
            user_id=viewer_id,
            username=viewer_username,
            action="mini_profile_opened",
            details=(
                f"Открыт мини-профиль target_user={uid} "
                f"target_username={target_username}"
            ),
        )

    return UserMiniProfileOut(
        id=uid,
        username=user.username,
        avatar_name=user.avatar_name,
        role=target_role,
        deleted=bool(user.deleted_at),
        registered_at=user.registered_at,
        last_visit_at=user.last_visit_at,
        last_game_at=last_game_at,
        last_game_id=last_game_id,
        online=online,
        subscription_active=theme_state.subscription_active,
        profile_theme_color=theme_state.color,
        profile_theme_icon=theme_state.icon,
        friend_status=friend_status,
        friends_count=int(friends_count or 0),
        admin_friends=admin_friends,
        active_sanction=active_sanction,
        nomination_stats=nomination_stats,
    )


@router.get("/{user_id}/nickname_history", response_model=UserNicknameHistoryOut)
@log_route("users.nickname_history")
@rate_limited(lambda ident, user_id, **_: f"rl:user_nickname_history:{ident['id']}:{user_id}", limit=10, window_s=1)
async def nickname_history(user_id: int, allow_deleted: bool = False, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserNicknameHistoryOut:
    viewer_role = str(ident["role"] or "").strip().lower()
    is_staff_viewer = viewer_role in {"admin", "moder"}
    uid = int(user_id)
    if uid <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    target_role = str(user.role or "user").strip().lower()
    if target_role == "admin" and viewer_role != "admin":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if user.deleted_at and not (allow_deleted and is_staff_viewer):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    return UserNicknameHistoryOut(items=build_nickname_history_out(user.username, user.nickname_history))


@router.delete("/nickname_history", response_model=UserNicknameHistoryOut)
@log_route("users.clear_nickname_history")
@rate_limited(lambda ident, **_: f"rl:clear_nickname_history:{ident['id']}", limit=2, window_s=1)
async def clear_nickname_history(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserNicknameHistoryOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    await ensure_profile_changes_allowed(db, uid)
    theme_state = await resolve_profile_theme_state(db, uid)
    if not theme_state.subscription_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="subscription_required")

    nickname_history_before = build_nickname_history_out(user.username, user.nickname_history)
    user.nickname_history = serialize_nickname_history([])
    await db.commit()
    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="nickname_history_cleared",
        details=(
            f"Очистка истории никнеймов: user_id={uid} "
            f"history={' -> '.join(nickname_history_before) or '-'}"
        ),
    )

    return UserNicknameHistoryOut(items=build_nickname_history_out(user.username, user.nickname_history))


@router.post("/support_link_click", response_model=Ok)
@log_route("users.support_link_click")
@rate_limited(lambda ident, **_: f"rl:support_link_click:{ident['id']}", limit=10, window_s=1)
async def support_link_click(payload: SupportLinkClickIn | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    username = str(ident["username"] or "")
    site_name = non_empty_str(payload.site_name if payload else None) or "-"
    await log_action(
        db,
        user_id=uid,
        username=username,
        action="support_link_click",
        details=f"Переход по ссылке поддержки: user_id={uid} site_name={site_name}",
    )
    return Ok()


@router.post("/contact_request", response_model=Ok)
@log_route("users.contact_request")
@rate_limited(contact_request_rate_key, limit=3, window_s=60)
async def contact_request(request: Request, payload: ContactRequestIn, ident: Identity | None = Depends(get_identity_optional), db: AsyncSession = Depends(get_session)) -> Ok:
    category = non_empty_str(payload.category)
    topic = non_empty_str(payload.topic)
    text = non_empty_str(payload.text)
    contact = non_empty_str(payload.contact)
    if not category:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="category_empty")

    if not topic:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="topic_empty")

    if not text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text_empty")

    if not contact:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="contact_empty")

    uid = int(ident["id"]) if ident else None
    db_username: str | None = None
    db_role: str | None = None
    db_telegram_id = 0
    if uid is not None:
        user = await db.get(User, uid)
        if user and not user.deleted_at:
            db_username = str(user.username or ident.get("username") or f"user{uid}")
            db_role = str(user.role or ident.get("role") or "")
            db_telegram_id = int(user.telegram_id or 0)

    user_lines = ["Пользователь сайта: гость"]
    if uid is not None and db_username is not None:
        user_lines = [
            "Пользователь сайта: зарегистрирован",
            f"Ник: {db_username}",
            f"ID пользователя: {uid}",
            f"Роль: {db_role or '-'}",
            f"TG ID из БД: {db_telegram_id if db_telegram_id > 0 else 'не привязан'}",
        ]
    user_block = "\n".join(user_lines)

    message = (
        "Новое обращение с сайта\n\n"
        f"{user_block}\n\n"
        f"Контакт для обратной связи: {contact}\n\n"
        f"Категория: {category}\n"
        f"Тема: {topic}\n\n"
        f"Текст обращения:\n{text}"
    )

    send_result = await send_text_message(chat_id=CONTACT_REQUEST_TELEGRAM_ID, text=message)
    if not send_result.ok:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=send_result.reason or "telegram_unavailable")

    with suppress(Exception):
        await log_action(
            db,
            user_id=uid,
            username=db_username,
            action="contact_request_sent",
            details=f"Отправлено обращение: user_id={uid or '-'} category={category} topic={topic}",
        )

    return Ok()


@router.get("/games/history", response_model=UserGamesHistoryOut)
@log_route("users.games_history")
@rate_limited(lambda ident, **_: f"rl:games_history:{ident['id']}", limit=10, window_s=1)
async def games_history(page: int = 1, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserGamesHistoryOut:
    await ensure_verification_allowed(db, int(ident["id"]))
    return await fetch_games_history_page(db, page=page, per_page=GAME_HISTORY_PER_PAGE)


@router.get("/games/history/personal", response_model=UserGamesHistoryOut)
@log_route("users.games_history_personal")
@rate_limited(lambda ident, **_: f"rl:games_history_personal:{ident['id']}", limit=10, window_s=1)
async def games_history_personal(page: int = 1, role: Literal["citizen", "mafia", "don", "sheriff"] | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserGamesHistoryOut:
    await ensure_verification_allowed(db, int(ident["id"]))
    uid = safe_int((ident or {}).get("id"))
    return await fetch_games_history_page(
        db,
        page=page,
        player_uid=uid,
        player_role=role,
        per_page=PERSONAL_GAME_HISTORY_PER_PAGE,
    )


@router.get("/games/history/{game_id}", response_model=GameHistoryItemOut)
@log_route("users.game_history_details")
@rate_limited(lambda ident, game_id=None, **_: f"rl:game_history_details:{ident['id']}:{game_id}", limit=10, window_s=1)
async def game_history_details(game_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> GameHistoryItemOut:
    await ensure_verification_allowed(db, int(ident["id"]))
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
    leave_map: dict[int, tuple[int, str, list[int], bool]] = {}
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
                leave_is_ppk = False
                if leave_reason == "foul":
                    leave_is_ppk = bool(action.get("ppk")) or str(action.get("format") or "").strip().upper() == "PPK"
                leave_map[target_uid] = (leave_day, leave_reason, voted_by_user_ids, leave_is_ppk)
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
        profile_role = non_empty_str((profile or {}).get("role"))
        deleted_at_value = non_empty_str((profile or {}).get("deleted_at"))
        role_value = None
        points = 0
        mmr = 0
        leave_day_value = None
        leave_reason_value = None
        leave_ppk_value = False
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
                leave_ppk_value = bool(leave_data[3]) if leave_reason_value == "foul" else False
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
                profile_role=profile_role,
                deleted=deleted_at_value is not None,
                role=role_value,
                points=points,
                mmr=mmr,
                leave_day=leave_day_value,
                leave_reason=leave_reason_value,
                leave_ppk=leave_ppk_value,
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


@router.get("/sanctions", response_model=UserSanctionsOut)
@log_route("users.sanctions_history")
@rate_limited(lambda ident, **_: f"rl:sanctions_history:{ident['id']}", limit=10, window_s=1)
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


@router.patch("/username", response_model=UsernameUpdateOut)
@log_route("users.update_username")
@rate_limited(lambda ident, **_: f"rl:update_username:{ident['id']}", limit=1, window_s=1)
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
    next_nickname_history = prepend_nickname_history(user.nickname_history, old_username, current_username=new)
    await db.execute(
        update(User)
        .where(User.id == uid)
        .values(username=new, nickname_history=next_nickname_history)
    )
    await db.commit()
    theme_state = await resolve_profile_theme_state(db, uid)
    await write_user_profile_cache(
        uid,
        username=new,
        role=str(user.role),
        avatar_name=user.avatar_name,
        theme_color=theme_state.color,
        theme_until=theme_state.subscription_until,
        theme_icon=theme_state.icon,
    )

    await log_action(
        db,
        user_id=uid,
        username=new,
        action="username_updated",
        details=f"Изменение никнейма: {old_username} -> {new}",
    )

    await broadcast_creator_rooms(uid, update_name=new)
    await emit_global_chat_messages_refresh()
    return UsernameUpdateOut(username=new)


@router.get("/chat/mentions", response_model=ChatMentionSearchOut)
@rate_limited(lambda ident, **_: f"rl:chat_mentions_search:{ident['id']}", limit=CHAT_MENTION_SEARCH_RATE_LIMIT, window_s=CHAT_MENTION_SEARCH_RATE_WINDOW_S)
async def search_chat_mentions(query: str, limit: int = CHAT_MENTION_LIMIT_DEFAULT, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> ChatMentionSearchOut:
    normalized_query = normalize_chat_mention_query(query)
    normalized_limit = max(1, min(int(limit or CHAT_MENTION_LIMIT_DEFAULT), CHAT_MENTION_LIMIT_MAX))
    query_lower = normalized_query.lower()
    rows = await db.execute(
        select(User.id, User.username, User.avatar_name)
        .where(
            User.deleted_at.is_(None),
            func.lower(User.username).like(f"{query_lower}%"),
        )
        .order_by(
            case((func.lower(User.username) == query_lower, 0), else_=1).asc(),
            func.length(User.username).asc(),
            func.lower(User.username).asc(),
            User.id.asc(),
        )
        .limit(normalized_limit)
    )
    return ChatMentionSearchOut(
        items=[
            ChatMentionUserOut(
                id=int(user_id),
                username=str(username),
                avatar_name=cast(str | None, avatar_name),
            )
            for user_id, username, avatar_name in rows.all()
            if user_id is not None and username is not None
        ]
    )


@router.patch("/ui_prefs", response_model=UserUiPrefsOut)
@log_route("users.update_ui_prefs")
@rate_limited(lambda ident, **_: f"rl:update_ui_prefs:{ident['id']}", limit=10, window_s=1)
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


@router.patch("/profile_theme", response_model=UserProfileThemeOut)
@log_route("users.update_profile_theme")
@rate_limited(lambda ident, **_: f"rl:update_profile_theme:{ident['id']}", limit=2, window_s=1)
async def update_profile_theme(payload: UserProfileThemeIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> UserProfileThemeOut:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    await ensure_profile_changes_allowed(db, uid)
    theme_state = await resolve_profile_theme_state(db, uid)
    if not theme_state.subscription_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="subscription_required")
    defaults_changed = await ensure_profile_theme_defaults(db, uid)
    if defaults_changed:
        await db.commit()
        theme_state = await resolve_profile_theme_state(db, uid)

    try:
        color = normalize_profile_theme_color(payload.color, role=user.role)
    except ValueError as exc:
        detail = str(exc).strip() or "profile_theme_invalid"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    has_icon_update = "icon" in payload.model_fields_set
    if has_icon_update:
        try:
            icon = normalize_profile_theme_icon(payload.icon)
        except ValueError as exc:
            detail = str(exc).strip() or "profile_theme_icon_invalid"
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    else:
        icon = theme_state.icon

    if theme_state.color == color and (not has_icon_update or theme_state.icon == icon):
        if defaults_changed:
            await refresh_user_profile_cache(db, uid)
            with suppress(Exception):
                await emit_auth_profile_sync(uid, role=str(user.role))
            with suppress(Exception):
                await emit_room_profile_theme_sync(uid, theme_state.color, theme_state.icon)
            with suppress(Exception):
                from ...services.global_chat import emit_global_chat_profile_theme_sync
                await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
        return UserProfileThemeOut(
            subscription_active=True,
            subscription_started_at=theme_state.subscription_started_at,
            subscription_until=theme_state.subscription_until,
            profile_theme_color=theme_state.color,
            profile_theme_icon=theme_state.icon,
        )

    old_color = theme_state.color
    old_icon = theme_state.icon
    changed_theme_parts: list[str] = []
    if old_color != color:
        changed_theme_parts.append(f"profile_theme_color: {old_color or 'none'} -> {color}")
    if has_icon_update and old_icon != icon:
        changed_theme_parts.append(f"profile_theme_icon: {old_icon or 'none'} -> {icon}")

    await upsert_profile_theme_preference(db, uid, color)
    if has_icon_update:
        await upsert_profile_theme_icon_preference(db, uid, icon)
    await db.commit()
    await refresh_user_profile_cache(db, uid)
    next_state = await resolve_profile_theme_state(db, uid)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="profile_theme_updated",
        details=f"Обновление темы профиля: user_id={uid} changes={'; '.join(changed_theme_parts)}",
    )

    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(uid, next_state.color, next_state.icon)
    with suppress(Exception):
        from ...services.global_chat import emit_global_chat_profile_theme_sync
        await emit_global_chat_profile_theme_sync(uid, next_state.color, next_state.icon)

    return UserProfileThemeOut(
        subscription_active=next_state.subscription_active,
        subscription_started_at=next_state.subscription_started_at,
        subscription_until=next_state.subscription_until,
        profile_theme_color=next_state.color,
        profile_theme_icon=next_state.icon,
    )


@router.patch("/password", response_model=Ok)
@log_route("users.change_password")
@rate_limited(lambda ident, **_: f"rl:change_password:{ident['id']}", limit=1, window_s=1)
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

    new_password = normalize_password(payload.new_password)
    user.password_hash = hash_password(new_password)
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


@router.post("/unverify", response_model=Ok)
@log_route("users.unverify_telegram")
@rate_limited(lambda ident, **_: f"rl:unverify_telegram:{ident['id']}", limit=1, window_s=1)
async def unverify_telegram(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if user.deleted_at:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_deleted")

    active = await fetch_active_sanctions(db, uid)
    if pick_active_sanction_kind(active):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="sanction_active")

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
    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role or ident.get("role") or "user"))
    with suppress(Exception):
        await emit_global_chat_permissions_updated(uid)

    return Ok()


@router.post("/avatar", response_model=AvatarUploadOut)
@log_route("users.upload_avatar")
@rate_limited(lambda ident, **_: f"rl:upload_avatar:{ident['id']}", limit=1, window_s=1)
async def upload_avatar(file: UploadFile = File(...), static_frame_index: int | None = Form(None), ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> AvatarUploadOut:
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
    if ct not in AVATAR_ALLOWED_CT:
        raise HTTPException(status_code=415, detail="unsupported_media_type")

    theme_state = await resolve_profile_theme_state(db, uid)
    if ct == "image/gif" and not theme_state.subscription_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="subscription_required")
    gif_static_frame_index = int(static_frame_index or 0)
    if ct != "image/gif":
        gif_static_frame_index = 0

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty_file")

    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    name = await put_avatar_async(uid, data, ct, static_frame_index=gif_static_frame_index)
    if not name:
        raise HTTPException(status_code=422, detail="bad_image")

    await db.execute(update(User).where(User.id == uid).values(avatar_name=name))
    await db.commit()
    await write_user_profile_cache(
        uid,
        username=db_username,
        role=db_role,
        avatar_name=name,
        theme_color=theme_state.color,
        theme_until=theme_state.subscription_until,
        theme_icon=theme_state.icon,
    )
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


@router.post("/chat/image/presign", response_model=ChatImagePresignOut)
@log_route("users.presign_chat_image")
@rate_limited(lambda ident, **_: f"rl:presign_chat_image:{ident['id']}", limit=5, window_s=10)
async def presign_chat_image(payload: ChatImagePresignIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> ChatImagePresignOut:
    uid = int(ident["id"])
    permissions = await resolve_global_chat_permissions(db, uid)
    if not permissions.can_open:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=permissions.error or "forbidden")

    if not permissions.can_send:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=global_chat_send_error(permissions))

    ct = (payload.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_media_type")

    key = build_chat_image_object_name(uid, ct)
    upload_url, upload_fields, expires_in = await build_chat_image_post_upload_async(key, ct, expires_minutes=15)
    return ChatImagePresignOut(
        image_object_key=key,
        upload_url=upload_url,
        expires_in=expires_in,
        content_type=ct,
        upload_method="POST",
        upload_fields=upload_fields,
    )


@router.post("/chat/image", response_model=ChatImageUploadOut)
@log_route("users.upload_chat_image")
@rate_limited(lambda ident, **_: f"rl:upload_chat_image:{ident['id']}", limit=3, window_s=10)
async def upload_chat_image(file: UploadFile = File(...), ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> ChatImageUploadOut:
    uid = int(ident["id"])
    permissions = await resolve_global_chat_permissions(db, uid)
    if not permissions.can_open:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=permissions.error or "forbidden")

    if not permissions.can_send:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=global_chat_send_error(permissions))

    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CT:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_media_type")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="empty_file")

    if len(data) > CHAT_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")

    key = await put_chat_image_async(uid, data, ct)
    if not key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bad_image")

    return ChatImageUploadOut(image_object_key=key)


@router.delete("/chat/image", response_model=Ok)
@log_route("users.delete_chat_image")
@rate_limited(lambda ident, **_: f"rl:delete_chat_image:{ident['id']}", limit=10, window_s=10)
async def delete_chat_image(key: str, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    try:
        normalized_key = normalize_global_chat_image_object_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc) or "bad_image_key")

    if not normalized_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bad_image_key")

    try:
        ensure_global_chat_image_owned_by_user(uid, normalized_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "forbidden")

    if await is_global_chat_image_referenced(db, normalized_key):
        return Ok()

    await delete_object_async(normalized_key)
    return Ok()


@router.delete("/avatar", response_model=Ok)
@log_route("users.delete_avatar")
@rate_limited(lambda ident, **_: f"rl:delete_avatar:{ident['id']}", limit=1, window_s=1)
async def delete_avatar(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    await ensure_profile_changes_allowed(db, uid)

    await delete_user_avatar(
        db,
        uid,
        missing_status_code=status.HTTP_401_UNAUTHORIZED,
        missing_detail="Unauthorized",
    )

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="avatar_deleted",
        details="Удаление аватара",
    )

    return Ok()


@router.delete("/account", response_model=Ok)
@log_route("users.delete_account")
@rate_limited(lambda ident, **_: f"rl:delete_account:{ident['id']}", limit=1, window_s=5)
async def delete_account(resp: Response, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if is_protected_admin(getattr(user, "id", 0)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="protected_user")

    if normalize_user_role(getattr(user, "role", None)) == ROLE_MODER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="staff_self_delete_forbidden")

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
