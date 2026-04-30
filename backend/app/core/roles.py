from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_MODER = "moder"
ROLE_USER = "user"

ROOM_ROLE_HEAD = "head"
ROOM_ROLE_HOST = "host"


def normalize_user_role(raw: object) -> str:
    value = str(raw or "").strip().lower()
    if value == ROLE_ADMIN:
        return ROLE_ADMIN

    if value == ROLE_MODER:
        return ROLE_MODER

    return ROLE_USER


def normalize_room_role(raw: object) -> str:
    value = str(raw or "").strip().lower()
    if value == ROOM_ROLE_HEAD:
        return ROOM_ROLE_HEAD

    if value == ROOM_ROLE_HOST:
        return ROOM_ROLE_HOST

    if value == ROLE_ADMIN:
        return ROLE_ADMIN

    if value == ROLE_MODER:
        return ROLE_MODER

    return ROLE_USER


def room_moderation_role(room_role: object, base_role: object | None = None) -> str:
    base_value = normalize_user_role(base_role)
    if base_value == ROLE_ADMIN:
        return ROLE_ADMIN

    if base_value == ROLE_MODER:
        return ROLE_MODER

    room_value = normalize_room_role(room_role)
    if room_value == ROOM_ROLE_HEAD:
        return ROOM_ROLE_HEAD

    if room_value == ROOM_ROLE_HOST:
        return ROOM_ROLE_HOST

    return ROLE_USER


def can_room_moderate(*, actor_room_role: object, target_room_role: object, actor_base_role: object | None = None, target_base_role: object | None = None) -> bool:
    actor_role = room_moderation_role(actor_room_role, actor_base_role)
    target_role = room_moderation_role(target_room_role, target_base_role)

    if actor_role == target_role:
        return False

    if actor_role == ROLE_ADMIN:
        return target_role in {ROLE_MODER, ROOM_ROLE_HOST, ROLE_USER}

    if actor_role in {ROLE_MODER, ROOM_ROLE_HOST}:
        return target_role == ROLE_USER

    return False


def is_chat_moderator_role(raw: object) -> bool:
    return normalize_user_role(raw) in {ROLE_ADMIN, ROLE_MODER}


def can_moderate_chat_message(*, actor_role: object, target_role: object, actor_user_id: int | None = None, target_user_id: int | None = None) -> bool:
    actor_id = int(actor_user_id or 0)
    target_id = int(target_user_id or 0)
    if 0 < actor_id == target_id > 0:
        return True

    actor_value = normalize_user_role(actor_role)
    target_value = normalize_user_role(target_role)

    if actor_value == ROLE_ADMIN:
        return True

    if actor_value == ROLE_MODER:
        return target_value != ROLE_ADMIN

    return False


def can_view_deleted_chat_message(*, actor_role: object) -> bool:
    return normalize_user_role(actor_role) in {ROLE_ADMIN, ROLE_MODER}


def can_purge_deleted_chat_message(*, actor_role: object) -> bool:
    return normalize_user_role(actor_role) == ROLE_ADMIN


def admin_users_role_sort_value(raw: object) -> tuple[int, str]:
    value = str(raw or "").strip().casefold()
    if value == ROLE_ADMIN:
        return 0, value

    if value == ROLE_MODER:
        return 1, value

    if value == ROLE_USER:
        return 2, value

    return 3, value
