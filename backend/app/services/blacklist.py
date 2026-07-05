from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
import structlog
from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..models.friend import FriendLink, UserBlacklist
from ..models.subscription import UserSubscription
from ..models.user import User
from ..realtime.sio import sio
from ..services.user_cache import get_user_profiles_cached

log = structlog.get_logger()


def _positive_int(raw: object) -> int:
    try:
        value = int(raw)
    except Exception:
        return 0

    return value if value > 0 else 0


def _normalize_user_ids(raw: Iterable[int | str] | None) -> tuple[int, ...]:
    seen: set[int] = set()
    out: list[int] = []
    for item in raw or ():
        uid = _positive_int(item)
        if uid <= 0 or uid in seen:
            continue
        seen.add(uid)
        out.append(uid)
    return tuple(out)


async def user_has_active_subscription(session: AsyncSession, user_id: int, *, now: datetime | None = None) -> bool:
    uid = _positive_int(user_id)
    if uid <= 0:
        return False

    current = now or datetime.now(timezone.utc)
    subscription_id = await session.scalar(
        select(UserSubscription.id)
        .where(
            UserSubscription.user_id == uid,
            UserSubscription.starts_at <= current,
            UserSubscription.ends_at > current,
        )
        .limit(1)
    )
    return subscription_id is not None


async def ensure_blacklist_subscription(session: AsyncSession, user_id: int) -> None:
    if not await user_has_active_subscription(session, user_id):
        await clear_user_blacklist(session, user_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="subscription_required")


async def is_user_blacklisted_by(session: AsyncSession, *, owner_id: int, target_id: int) -> bool:
    owner = _positive_int(owner_id)
    target = _positive_int(target_id)
    if owner <= 0 or target <= 0 or owner == target:
        return False

    row_id = await session.scalar(
        select(UserBlacklist.id)
        .where(UserBlacklist.owner_id == owner, UserBlacklist.target_id == target)
        .limit(1)
    )
    return row_id is not None


async def blacklist_relation(session: AsyncSession, user_a: int, user_b: int) -> dict[str, bool]:
    a = _positive_int(user_a)
    b = _positive_int(user_b)
    out = {"a_blocks_b": False, "b_blocks_a": False}
    if a <= 0 or b <= 0 or a == b:
        return out

    rows = await session.execute(
        select(UserBlacklist.owner_id, UserBlacklist.target_id).where(
            or_(
                and_(UserBlacklist.owner_id == a, UserBlacklist.target_id == b),
                and_(UserBlacklist.owner_id == b, UserBlacklist.target_id == a),
            )
        )
    )
    for owner_id_raw, target_id_raw in rows.all():
        owner_id = _positive_int(owner_id_raw)
        target_id = _positive_int(target_id_raw)
        if owner_id == a and target_id == b:
            out["a_blocks_b"] = True
        elif owner_id == b and target_id == a:
            out["b_blocks_a"] = True
    return out


async def raise_if_friend_request_blocked_by_blacklist(session: AsyncSession, *, requester_id: int, target_id: int) -> None:
    relation = await blacklist_relation(session, requester_id, target_id)
    if relation["a_blocks_b"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_blacklisted_by_me")

    if relation["b_blocks_a"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="requester_blacklisted_by_target")


async def filter_notification_targets_for_actor(session: AsyncSession, *, actor_id: int, target_ids: Iterable[int | str]) -> tuple[int, ...]:
    actor = _positive_int(actor_id)
    targets = _normalize_user_ids(target_ids)
    if actor <= 0 or not targets:
        return targets

    rows = await session.execute(
        select(UserBlacklist.owner_id).where(
            UserBlacklist.owner_id.in_(targets),
            UserBlacklist.target_id == actor,
        )
    )
    blocked_target_ids = {
        _positive_int(owner_id)
        for owner_id in rows.scalars().all()
        if _positive_int(owner_id) > 0
    }
    return tuple(uid for uid in targets if uid not in blocked_target_ids)


async def emit_blacklist_update(user_id: int, other_id: int, *, blacklisted: bool | None = None, blacklisted_by_target: bool | None = None, cleared: bool = False) -> None:
    payload: dict[str, Any] = {"user_id": int(other_id)}
    if blacklisted is not None:
        payload["blacklisted"] = bool(blacklisted)
    if blacklisted_by_target is not None:
        payload["blacklisted_by_target"] = bool(blacklisted_by_target)
    if cleared:
        payload["cleared"] = True
    with suppress(Exception):
        await sio.emit("blacklist_update", payload, room=f"user:{int(user_id)}", namespace="/auth")


async def emit_friends_status_none(user_id: int, other_id: int) -> None:
    with suppress(Exception):
        await sio.emit(
            "friends_update",
            {"user_id": int(other_id), "status": "none"},
            room=f"user:{int(user_id)}",
            namespace="/auth",
        )


async def _cleanup_private_room_access_for_blacklist(owner_id: int, target_id: int) -> None:
    owner = _positive_int(owner_id)
    target = _positive_int(target_id)
    if owner <= 0 or target <= 0:
        return

    try:
        r = get_redis()
        raw_room_ids = await r.smembers(f"user:{owner}:rooms")
    except Exception:
        log.warning("blacklist.room_access.rooms_load_failed", owner_id=owner, target_id=target)
        return

    room_ids = _normalize_user_ids(raw_room_ids)
    if not room_ids:
        return

    for room_id in room_ids:
        try:
            params = await r.hgetall(f"room:{room_id}:params")
            if not params or _positive_int(params.get("creator")) != owner:
                continue

            async with r.pipeline(transaction=True) as p:
                await p.srem(f"room:{room_id}:allow", str(target))
                await p.srem(f"room:{room_id}:pending", str(target))
                await p.zrem(f"room:{room_id}:requests", str(target))
                await p.srem(f"room:{room_id}:invited", str(target))
                removed_allow, removed_pending, removed_requests, _removed_invited = await p.execute()

            removed_any = bool(int(removed_allow or 0) or int(removed_pending or 0) or int(removed_requests or 0))
            if not removed_any:
                continue

            event_payload = {"room_id": int(room_id), "user_id": target, "source": "blacklist"}
            with suppress(Exception):
                await sio.emit("room_app_revoked", event_payload, room=f"user:{owner}", namespace="/auth")
            with suppress(Exception):
                await sio.emit("room_app_revoked", event_payload, room=f"user:{target}", namespace="/auth")
            if str(params.get("anonymity") or "visible") == "hidden":
                with suppress(Exception):
                    await sio.emit("rooms_remove", {"id": int(room_id)}, room=f"user:{target}", namespace="/rooms")
        except Exception:
            log.warning("blacklist.room_access.cleanup_failed", owner_id=owner, target_id=target, room_id=room_id)


async def add_user_to_blacklist(session: AsyncSession, *, owner_id: int, target_id: int) -> tuple[bool, tuple[int, ...]]:
    owner = _positive_int(owner_id)
    target = _positive_int(target_id)
    if owner <= 0 or target <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if owner == target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_blacklist")

    await ensure_blacklist_subscription(session, owner)

    target_user = await session.get(User, target)
    if target_user is None or target_user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    deleted_friend_ids: set[int] = set()
    link = await session.scalar(
        select(FriendLink)
        .where(
            or_(
                and_(FriendLink.requester_id == owner, FriendLink.addressee_id == target),
                and_(FriendLink.requester_id == target, FriendLink.addressee_id == owner),
            )
        )
        .limit(1)
    )
    if link is not None:
        deleted_friend_ids.update((owner, target))
        await session.delete(link)
        await session.flush()

    stmt = (
        insert(UserBlacklist)
        .values(owner_id=owner, target_id=target)
        .on_conflict_do_nothing(index_elements=["owner_id", "target_id"])
        .returning(UserBlacklist.id)
    )
    inserted_id = await session.scalar(stmt)
    await session.commit()

    created = inserted_id is not None
    if deleted_friend_ids:
        await emit_friends_status_none(owner, target)
        await emit_friends_status_none(target, owner)

    if created:
        await emit_blacklist_update(owner, target, blacklisted=True)
        await emit_blacklist_update(target, owner, blacklisted_by_target=True)
        await _cleanup_private_room_access_for_blacklist(owner, target)
    return created, tuple(sorted(uid for uid in deleted_friend_ids if uid > 0))


async def remove_user_from_blacklist(session: AsyncSession, *, owner_id: int, target_id: int) -> bool:
    owner = _positive_int(owner_id)
    target = _positive_int(target_id)
    if owner <= 0 or target <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if owner == target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_blacklist")

    deleted = await session.execute(
        delete(UserBlacklist).where(
            UserBlacklist.owner_id == owner,
            UserBlacklist.target_id == target,
        )
    )
    removed = int(deleted.rowcount or 0) > 0
    await session.commit()
    if removed:
        await emit_blacklist_update(owner, target, blacklisted=False)
        await emit_blacklist_update(target, owner, blacklisted_by_target=False)
    return removed


async def clear_user_blacklist(session: AsyncSession, owner_id: int) -> tuple[int, ...]:
    owner = _positive_int(owner_id)
    if owner <= 0:
        return ()

    rows = await session.execute(
        select(UserBlacklist.target_id).where(UserBlacklist.owner_id == owner)
    )
    target_ids = _normalize_user_ids(rows.scalars().all())
    if not target_ids:
        return ()

    await session.execute(delete(UserBlacklist).where(UserBlacklist.owner_id == owner))
    await session.commit()

    for target_id in target_ids:
        await emit_blacklist_update(owner, target_id, blacklisted=False, cleared=True)
        await emit_blacklist_update(target_id, owner, blacklisted_by_target=False, cleared=True)
    return target_ids


async def clear_user_blacklist_if_subscription_inactive(session: AsyncSession, owner_id: int) -> tuple[int, ...]:
    owner = _positive_int(owner_id)
    if owner <= 0:
        return ()

    if await user_has_active_subscription(session, owner):
        return ()

    return await clear_user_blacklist(session, owner)


async def build_blacklist_items(session: AsyncSession, owner_id: int) -> list[dict[str, Any]]:
    owner = _positive_int(owner_id)
    if owner <= 0:
        return []

    rows = await session.execute(
        select(UserBlacklist.target_id, UserBlacklist.created_at)
        .where(UserBlacklist.owner_id == owner)
        .order_by(UserBlacklist.created_at.desc(), UserBlacklist.id.desc())
    )
    pairs = [
        (_positive_int(target_id), created_at)
        for target_id, created_at in rows.all()
        if _positive_int(target_id) > 0
    ]
    if not pairs:
        return []

    target_ids = [target_id for target_id, _ in pairs]
    profiles = await get_user_profiles_cached(session, target_ids)
    items: list[dict[str, Any]] = []
    for target_id, created_at in pairs:
        profile = profiles.get(target_id) or {}
        items.append(
            {
                "id": target_id,
                "username": profile.get("username"),
                "avatar_name": profile.get("avatar_name"),
                "role": profile.get("role"),
                "theme_color": profile.get("theme_color"),
                "theme_icon": profile.get("theme_icon"),
                "created_at": created_at,
            }
        )
    return items
