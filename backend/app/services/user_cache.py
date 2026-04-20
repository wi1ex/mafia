from __future__ import annotations
import structlog
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Iterable, TypedDict
from ..core.clients import get_redis
from ..models.user import User
from ..services.profile_theme import resolve_profile_theme_state, resolve_profile_theme_states

log = structlog.get_logger()

PROFILE_FIELDS: tuple[str, ...] = ("username", "avatar_name", "role", "theme_color", "theme_until", "theme_icon", "deleted_at")


class UserProfile(TypedDict):
    username: str | None
    avatar_name: str | None
    role: str | None
    theme_color: str | None
    theme_until: str | None
    theme_icon: str | None
    deleted_at: str | None


def user_profile_cache_key(user_id: int) -> str:
    return f"user:{int(user_id)}:profile"


def _normalize_user_ids(user_ids: Iterable[int | str]) -> list[int]:
    ids: set[int] = set()
    for raw in user_ids:
        try:
            uid = int(raw)
        except Exception:
            continue
        if uid > 0:
            ids.add(uid)
    return sorted(ids)


def _value_or_none(raw: Any) -> str | None:
    if raw is None:
        return None

    try:
        value = str(raw).strip()
    except Exception:
        return None

    return value or None


def _profile_from_values(values: list[Any] | tuple[Any, ...]) -> UserProfile:
    username = _value_or_none(values[0] if len(values) > 0 else None)
    avatar_name = _value_or_none(values[1] if len(values) > 1 else None)
    role = _value_or_none(values[2] if len(values) > 2 else None)
    theme_color = _value_or_none(values[3] if len(values) > 3 else None)
    theme_until = _value_or_none(values[4] if len(values) > 4 else None)
    theme_icon = _value_or_none(values[5] if len(values) > 5 else None)
    deleted_at = _value_or_none(values[6] if len(values) > 6 else None)
    return {
        "username": username,
        "avatar_name": avatar_name,
        "role": role,
        "theme_color": theme_color,
        "theme_until": theme_until,
        "theme_icon": theme_icon,
        "deleted_at": deleted_at,
    }


def _profile_ready(profile: UserProfile | None) -> bool:
    if not profile:
        return False

    if not (bool(profile.get("username")) and bool(profile.get("role"))):
        return False

    if profile.get("theme_color") is not None and profile.get("theme_until") is not None:
        return profile.get("theme_icon") is not None

    return True


def _parse_datetime_or_none(raw: Any) -> datetime | None:
    value = _value_or_none(raw)
    if value is None:
        return None

    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except Exception:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_theme_state(profile: UserProfile) -> UserProfile:
    theme_color = _value_or_none(profile.get("theme_color"))
    theme_until = _value_or_none(profile.get("theme_until"))
    theme_icon = _value_or_none(profile.get("theme_icon"))
    if theme_color is None or theme_until is None:
        profile["theme_color"] = None
        profile["theme_until"] = None
        profile["theme_icon"] = None
        return profile

    expires_at = _parse_datetime_or_none(theme_until)
    if expires_at is None or expires_at <= datetime.now(timezone.utc):
        profile["theme_color"] = None
        profile["theme_until"] = None
        profile["theme_icon"] = None
        return profile

    profile["theme_color"] = theme_color
    profile["theme_until"] = theme_until
    profile["theme_icon"] = theme_icon
    return profile


def _avatar_object_key(avatar_name: str) -> str:
    avatar = avatar_name.strip()
    if not avatar:
        return ""

    if avatar.startswith("avatars/"):
        return avatar

    return f"avatars/{avatar}"


async def read_user_profile_cache(user_id: int, *, redis_client=None) -> UserProfile | None:
    r = redis_client or get_redis()
    key = user_profile_cache_key(user_id)
    try:
        values = await r.hmget(key, *PROFILE_FIELDS)
    except Exception:
        log.warning("user_cache.read_failed", user_id=int(user_id))
        return None

    if not isinstance(values, (list, tuple)):
        return None

    profile = _normalize_theme_state(_profile_from_values(values))
    return profile if _profile_ready(profile) else None


async def write_user_profile_cache(user_id: int, *, username: str, role: str, avatar_name: str | None, theme_color: str | None, theme_until: datetime | None, theme_icon: str | None = None, deleted_at: datetime | str | None = None, redis_client=None) -> None:
    r = redis_client or get_redis()
    key = user_profile_cache_key(user_id)
    mapping = {
        "username": str(username),
        "role": str(role),
    }
    avatar = _value_or_none(avatar_name)
    color = _value_or_none(theme_color)
    icon = _value_or_none(theme_icon)
    expires_at = theme_until.isoformat() if isinstance(theme_until, datetime) else None
    deleted_at_value = deleted_at.isoformat() if isinstance(deleted_at, datetime) else _value_or_none(deleted_at)

    try:
        async with r.pipeline() as p:
            await p.hset(key, mapping=mapping)
            if avatar is not None:
                await p.hset(key, mapping={"avatar_name": avatar})
            else:
                await p.hdel(key, "avatar_name")
            if color is not None and expires_at and icon is not None:
                await p.hset(key, mapping={"theme_color": color, "theme_until": expires_at, "theme_icon": icon})
            else:
                await p.hdel(key, "theme_color", "theme_until", "theme_icon")
            if deleted_at_value is not None:
                await p.hset(key, mapping={"deleted_at": deleted_at_value})
            else:
                await p.hdel(key, "deleted_at")
            await p.execute()
    except Exception:
        log.warning("user_cache.write_failed", user_id=int(user_id))


async def delete_user_profile_cache(user_id: int, *, redis_client=None) -> None:
    r = redis_client or get_redis()
    try:
        await r.delete(user_profile_cache_key(user_id))
    except Exception:
        log.warning("user_cache.delete_failed", user_id=int(user_id))


async def invalidate_avatar_presign_cache(avatar_name: str | None, *, redis_client=None) -> None:
    avatar = _value_or_none(avatar_name)
    if avatar is None:
        return

    key = _avatar_object_key(avatar)
    if not key:
        return

    r = redis_client or get_redis()
    try:
        keys = [f"presign:{key}"]
        if key.lower().endswith(".gif"):
            keys.append(f"presign:{key[:-4]}.png")
        await r.delete(*keys)
    except Exception:
        log.warning("user_cache.avatar_presign_invalidate_failed")


async def refresh_user_profile_cache(session: AsyncSession, user_id: int, *, redis_client=None) -> UserProfile | None:
    uid = int(user_id)
    row = await session.execute(select(User.username, User.avatar_name, User.role, User.deleted_at).where(User.id == uid))
    rec = row.first()
    if not rec:
        await delete_user_profile_cache(uid, redis_client=redis_client)
        return None

    theme_state = await resolve_profile_theme_state(session, uid)
    profile: UserProfile = {
        "username": _value_or_none(rec[0]),
        "avatar_name": _value_or_none(rec[1]),
        "role": _value_or_none(rec[2]),
        "theme_color": _value_or_none(theme_state.color),
        "theme_until": theme_state.subscription_until.isoformat() if theme_state.subscription_until else None,
        "theme_icon": _value_or_none(theme_state.icon),
        "deleted_at": rec[3].isoformat() if isinstance(rec[3], datetime) else _value_or_none(rec[3]),
    }
    if not _profile_ready(profile):
        await delete_user_profile_cache(uid, redis_client=redis_client)
        return None

    await write_user_profile_cache(
        uid,
        username=profile["username"] or "",
        role=profile["role"] or "user",
        avatar_name=profile["avatar_name"],
        theme_color=profile["theme_color"],
        theme_until=theme_state.subscription_until,
        theme_icon=profile["theme_icon"],
        deleted_at=profile["deleted_at"],
        redis_client=redis_client,
    )
    return profile


async def get_user_profile_cached(session: AsyncSession, user_id: int, *, redis_client=None) -> UserProfile | None:
    uid = int(user_id)
    cached = await read_user_profile_cache(uid, redis_client=redis_client)
    if cached:
        return cached

    return await refresh_user_profile_cache(session, uid, redis_client=redis_client)


async def get_user_profiles_cached(session: AsyncSession, user_ids: Iterable[int | str], *, redis_client=None) -> dict[int, UserProfile]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    r = redis_client or get_redis()
    raw_rows: list[Any] = []
    try:
        async with r.pipeline() as p:
            for uid in ids:
                await p.hmget(user_profile_cache_key(uid), *PROFILE_FIELDS)
            raw_rows = await p.execute()
    except Exception:
        raw_rows = [None for _ in ids]

    out: dict[int, UserProfile] = {}
    missed: list[int] = []
    for uid, raw in zip(ids, raw_rows):
        if not isinstance(raw, (list, tuple)):
            missed.append(uid)
            continue
        profile = _normalize_theme_state(_profile_from_values(raw))
        if _profile_ready(profile):
            out[uid] = profile
        else:
            missed.append(uid)

    if not missed:
        return out

    theme_states = await resolve_profile_theme_states(session, missed)
    rows = await session.execute(select(User.id, User.username, User.avatar_name, User.role, User.deleted_at).where(User.id.in_(missed)))
    db_map: dict[int, UserProfile] = {}
    for uid_raw, username, avatar_name, role, deleted_at in rows.all():
        try:
            uid = int(uid_raw)
        except Exception:
            continue
        theme_state = theme_states.get(uid)
        profile: UserProfile = {
            "username": _value_or_none(username),
            "avatar_name": _value_or_none(avatar_name),
            "role": _value_or_none(role),
            "theme_color": _value_or_none(theme_state.color if theme_state else None),
            "theme_until": (
                theme_state.subscription_until.isoformat()
                if theme_state and theme_state.subscription_until
                else None
            ),
            "theme_icon": _value_or_none(theme_state.icon if theme_state else None),
            "deleted_at": deleted_at.isoformat() if isinstance(deleted_at, datetime) else _value_or_none(deleted_at),
        }
        if _profile_ready(profile):
            db_map[uid] = profile

    try:
        async with r.pipeline() as p:
            for uid in missed:
                profile = db_map.get(uid)
                if not profile:
                    await p.delete(user_profile_cache_key(uid))
                    continue

                await p.hset(
                    user_profile_cache_key(uid),
                    mapping={
                        "username": profile["username"] or "",
                        "role": profile["role"] or "user",
                    },
                )
                if profile["avatar_name"] is not None:
                    await p.hset(user_profile_cache_key(uid), mapping={"avatar_name": profile["avatar_name"]})
                else:
                    await p.hdel(user_profile_cache_key(uid), "avatar_name")
                if profile["theme_color"] is not None and profile["theme_until"] is not None and profile["theme_icon"] is not None:
                    await p.hset(
                        user_profile_cache_key(uid),
                        mapping={
                            "theme_color": profile["theme_color"],
                            "theme_until": profile["theme_until"],
                            "theme_icon": profile["theme_icon"],
                        },
                    )
                else:
                    await p.hdel(user_profile_cache_key(uid), "theme_color", "theme_until", "theme_icon")
                if profile["deleted_at"] is not None:
                    await p.hset(user_profile_cache_key(uid), mapping={"deleted_at": profile["deleted_at"]})
                else:
                    await p.hdel(user_profile_cache_key(uid), "deleted_at")
            await p.execute()
    except Exception:
        log.warning("user_cache.batch_write_failed", users=len(missed))

    out.update(db_map)
    return out
