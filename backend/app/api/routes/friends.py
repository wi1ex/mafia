from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timezone
from time import time
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, delete, update, func, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.roles import ROLE_ADMIN, normalize_user_role
from ...core.settings import settings
from ...core.clients import get_redis
from ...core.logging import log_action
from ...models.friend import FriendLink, FriendCloseness
from ...models.user import User
from ...models.notif import Notif
from ...realtime.utils import filter_rooms_for_viewer, get_rooms_brief
from ...realtime.sio import sio
from ...services.telegram import send_text_message
from ...services.user_cache import get_user_profile_cached, get_user_profiles_cached
from ...schemas.common import Identity, Ok
from ...schemas.friend import FriendStatusOut, FriendsListOut, FriendsListItemOut, FriendIncomingCountOut, FriendInviteIn, BlacklistOut, BlacklistItemOut
from ...schemas.room import RoomBriefOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...services.blacklist import (
    add_user_to_blacklist,
    blacklist_relation,
    build_blacklist_items,
    clear_user_blacklist,
    raise_if_friend_request_blocked_by_blacklist,
    remove_user_from_blacklist,
    user_has_active_subscription,
)
from ...api.utils import (
    SANCTION_BAN,
    SANCTION_TIMEOUT,
    active_game_head_room_by_uid,
    active_alive_game_room_key,
    emit_rooms_upsert,
    fetch_active_sanctions,
    fetch_active_sanctions_for_users,
    fetch_online_user_ids,
    fetch_effective_online_user_ids,
    get_room_params_or_404,
    pair,
    load_link,
    raise_missing_incoming_request_error,
    raise_missing_outgoing_request_error,
    emit_notify,
    emit_friends_update,
    elapsed_seconds_since,
    require_friends_verification,
    tg_room_invite_cooldown_key,
)


router = APIRouter(dependencies=[Depends(require_friends_verification)])
FRIEND_REMOVE_MIN_SECONDS = 10 * 60
TG_ROOM_INVITE_COOLDOWN_S = 30 * 60
FRIEND_CLOSENESS_GAME_WEIGHT_SECONDS = 30 * 60


@router.get("/status/{user_id}", response_model=FriendStatusOut)
@log_route("friends.status")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:status:{ident['id']}:{user_id}", limit=10, window_s=1)
async def friend_status(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendStatusOut:
    uid = int(ident["id"])
    if user_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if user_id == uid:
        return FriendStatusOut(status="self")

    relation = await blacklist_relation(db, uid, int(user_id))
    if relation.get("a_blocks_b") or relation.get("b_blocks_a"):
        return FriendStatusOut(status="none")

    link = await load_link(db, uid, int(user_id))
    if not link:
        return FriendStatusOut(status="none")

    if link.status == "accepted":
        return FriendStatusOut(status="friends")

    if link.requester_id == uid:
        return FriendStatusOut(status="outgoing")

    return FriendStatusOut(status="incoming")


@router.get("/list", response_model=FriendsListOut)
@log_route("friends.list")
@rate_limited(lambda ident, **_: f"rl:friends:list:{ident['id']}", limit=10, window_s=1)
async def friends_list(room_id: int | None = None, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendsListOut:
    uid = int(ident["id"])
    accepted_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "accepted", or_(FriendLink.requester_id == uid, FriendLink.addressee_id == uid))
    )
    accepted = accepted_rows.scalars().all()

    incoming_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "pending", FriendLink.addressee_id == uid)
    )
    incoming = incoming_rows.scalars().all()

    outgoing_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "pending", FriendLink.requester_id == uid)
    )
    outgoing = outgoing_rows.scalars().all()

    friend_ids_all: list[int] = []
    for link in accepted:
        friend_ids_all.append(int(link.addressee_id if link.requester_id == uid else link.requester_id))

    incoming_ids = [int(x.requester_id) for x in incoming]
    outgoing_ids = [int(x.addressee_id) for x in outgoing]

    r = get_redis()
    base_online_ids = set(await fetch_online_user_ids(r))
    online_ids = await fetch_effective_online_user_ids(r, friend_ids_all, base_online_ids=base_online_ids)
    friend_ids: list[int] = friend_ids_all
    viewer_role = str(ident.get("role") or "user")

    all_ids = set(friend_ids + incoming_ids + outgoing_ids)
    users_map: dict[int, dict[str, object]] = {}
    if all_ids:
        profiles = await get_user_profiles_cached(db, all_ids)
        rows = await db.execute(
            select(
                User.id,
                User.telegram_id,
                User.tg_invites_enabled,
            ).where(User.id.in_(all_ids))
        )
        for rid, telegram_id, tg_invites_enabled in rows.all():
            uid_i = int(rid)
            profile = profiles.get(uid_i) or {}
            users_map[uid_i] = {
                "username": profile.get("username"),
                "avatar_name": profile.get("avatar_name"),
                "role": profile.get("role"),
                "theme_color": profile.get("theme_color"),
                "theme_icon": profile.get("theme_icon"),
                "telegram_verified": bool(telegram_id),
                "tg_invites_enabled": bool(tg_invites_enabled),
            }

    closeness_map: dict[tuple[int, int], int] = {}
    if friend_ids:
        pairs = [pair(uid, fid) for fid in friend_ids]
        if pairs:
            rows = await db.execute(
                select(
                    FriendCloseness.user_low,
                    FriendCloseness.user_high,
                    FriendCloseness.games_together,
                    FriendCloseness.room_seconds_together,
                )
                .where(tuple_(FriendCloseness.user_low, FriendCloseness.user_high).in_(pairs))
            )
            for lo, hi, games, room_seconds in rows.all():
                closeness_map[(int(lo), int(hi))] = (
                    max(0, int(games or 0)) * FRIEND_CLOSENESS_GAME_WEIGHT_SECONDS
                    + max(0, int(room_seconds or 0))
                )

    room_by_uid: dict[int, int] = {}
    room_candidates_by_uid: dict[int, int] = {}
    friends_with_online_room = [fid for fid in friend_ids if fid in online_ids]
    if friends_with_online_room:
        async with r.pipeline() as p:
            for fid in friends_with_online_room:
                await p.get(f"user:{int(fid)}:room")
            raw_rooms = await p.execute()

        for fid, raw in zip(friends_with_online_room, raw_rooms):
            try:
                rid = int(raw or 0)
            except Exception:
                rid = 0
            if rid > 0:
                room_candidates_by_uid[int(fid)] = rid

    if room_candidates_by_uid:
        try:
            candidate_items = list(room_candidates_by_uid.items())
            async with r.pipeline() as p:
                for fid, rid in candidate_items:
                    await p.sismember(f"room:{rid}:members", str(fid))
                raw_membership = await p.execute()

            for (fid, rid), is_member in zip(candidate_items, raw_membership):
                if bool(is_member):
                    room_by_uid[int(fid)] = int(rid)
        except Exception:
            room_by_uid = {}

    invite_room_id = int(room_id or 0)
    active_sanctions_by_uid = {}
    if invite_room_id > 0 and friend_ids:
        active_sanctions_by_uid = await fetch_active_sanctions_for_users(db, friend_ids)

    active_alive_game_room_by_uid: dict[int, int] = {}
    if friend_ids:
        try:
            async with r.pipeline() as p:
                for fid in friend_ids:
                    await p.get(active_alive_game_room_key(fid))
                raw_active_rooms = await p.execute()
        except Exception:
            raw_active_rooms = [None for _ in friend_ids]

        for fid, raw in zip(friend_ids, raw_active_rooms):
            try:
                rid = int(raw or 0)
            except Exception:
                rid = 0
            if rid > 0:
                active_alive_game_room_by_uid[int(fid)] = rid

    active_head_game_room_by_uid: dict[int, int] = {}
    if invite_room_id > 0 and friend_ids:
        active_head_game_room_by_uid = await active_game_head_room_by_uid(r, friend_ids)

    in_current_room_ids: set[int] = set()
    if invite_room_id > 0 and friend_ids:
        try:
            async with r.pipeline() as p:
                for fid in friend_ids:
                    await p.sismember(f"room:{invite_room_id}:members", str(fid))
                    await p.sismember(f"room:{invite_room_id}:spectators", str(fid))
                raw_in_room = await p.execute()
            for idx, fid in enumerate(friend_ids):
                is_member = bool(raw_in_room[idx * 2]) if idx * 2 < len(raw_in_room) else False
                is_spectator = bool(raw_in_room[idx * 2 + 1]) if idx * 2 + 1 < len(raw_in_room) else False
                if is_member or is_spectator:
                    in_current_room_ids.add(int(fid))
        except Exception:
            in_current_room_ids = set()

    invited_to_room_ids: set[int] = set()
    if invite_room_id > 0 and friend_ids:
        try:
            async with r.pipeline() as p:
                for fid in friend_ids:
                    await p.sismember(f"room:{invite_room_id}:invited", str(fid))
                raw_invited = await p.execute()
            for fid, is_invited in zip(friend_ids, raw_invited):
                if bool(is_invited):
                    invited_to_room_ids.add(int(fid))
        except Exception:
            invited_to_room_ids = set()

    tg_invite_cooldown_ids: set[int] = set()
    if invite_room_id > 0 and friend_ids:
        offline_friend_ids = [fid for fid in friend_ids if fid not in online_ids]
        if offline_friend_ids:
            try:
                async with r.pipeline() as p:
                    for fid in offline_friend_ids:
                        await p.exists(tg_room_invite_cooldown_key(fid))
                    raw_tg_cooldown = await p.execute()
                for fid, is_active in zip(offline_friend_ids, raw_tg_cooldown):
                    if bool(is_active):
                        tg_invite_cooldown_ids.add(int(fid))
            except Exception:
                tg_invite_cooldown_ids = set()

    rooms_map: dict[int, RoomBriefOut] = {}
    visible_room_ids: set[int] = set()
    room_ids = list({
        rid
        for rid in [*room_by_uid.values(), *active_alive_game_room_by_uid.values(), *active_head_game_room_by_uid.values()]
        if rid > 0
    })
    if room_ids:
        items = await get_rooms_brief(r, room_ids)
        items = await filter_rooms_for_viewer(r, items, viewer_role, uid)
        for item in items:
            try:
                out = RoomBriefOut(**item)
                rooms_map[int(out.id)] = out
                visible_room_ids.add(int(out.id))
            except Exception:
                continue

    def user_username(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("username")
        return str(raw) if isinstance(raw, str) else None

    def user_avatar_name(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("avatar_name")
        return str(raw) if isinstance(raw, str) else None

    def user_theme_color(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("theme_color")
        return str(raw) if isinstance(raw, str) else None

    def user_role(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("role")
        return str(raw) if isinstance(raw, str) else None

    def user_theme_icon(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("theme_icon")
        return str(raw) if isinstance(raw, str) else None

    def build_friend_item(fid: int) -> FriendsListItemOut:
        user_data = users_map.get(fid) or {}
        name = user_username(fid)
        avatar = user_avatar_name(fid)
        online = fid in online_ids
        closeness = closeness_map.get(pair(uid, fid), 0)
        rid = room_by_uid.get(fid) if online else None
        visible_rid = int(rid) if rid and int(rid) in visible_room_ids else None
        info = rooms_map.get(visible_rid) if visible_rid else None
        active_room_id = active_alive_game_room_by_uid.get(fid)
        active_head_room_id = active_head_game_room_by_uid.get(fid)
        active_sanctions = active_sanctions_by_uid.get(fid) or {}
        return FriendsListItemOut(
            kind="online" if online else "offline",
            id=int(fid),
            username=name,
            avatar_name=avatar,
            role=user_role(fid),
            theme_color=user_theme_color(fid),
            theme_icon=user_theme_icon(fid),
            online=online,
            closeness=closeness,
            room_id=visible_rid,
            room_title=info.title if info else None,
            room_in_game=bool(info.in_game) if info else None,
            in_current_room=(fid in in_current_room_ids) if invite_room_id > 0 else None,
            in_active_game_as_alive_player=bool(online and active_room_id),
            in_active_game_as_host=bool(active_head_room_id) if invite_room_id > 0 else None,
            telegram_verified=bool(user_data.get("telegram_verified")),
            tg_invites_enabled=bool(user_data.get("tg_invites_enabled")),
            room_invited=(fid in invited_to_room_ids) if invite_room_id > 0 else None,
            tg_invite_cooldown_active=(fid in tg_invite_cooldown_ids) if invite_room_id > 0 else None,
            ban_active=bool(active_sanctions.get(SANCTION_BAN)) if invite_room_id > 0 else None,
            timeout_active=bool(active_sanctions.get(SANCTION_TIMEOUT)) if invite_room_id > 0 else None,
        )

    friends_items: list[FriendsListItemOut] = []
    online_items: list[FriendsListItemOut] = []
    offline_items: list[FriendsListItemOut] = []
    if friend_ids:
        friends_items = [build_friend_item(fid) for fid in friend_ids]
        online_items = [f for f in friends_items if f.online]
        offline_items = [f for f in friends_items if not f.online]
        online_items.sort(key=lambda x: (-(x.closeness or 0), (x.username or f"user{x.id}").lower()))
        offline_items.sort(key=lambda x: (-(x.closeness or 0), (x.username or f"user{x.id}").lower()))

    incoming_items = [
        FriendsListItemOut(
            kind="incoming",
            id=int(link.requester_id),
            username=user_username(int(link.requester_id)),
            avatar_name=user_avatar_name(int(link.requester_id)),
            role=user_role(int(link.requester_id)),
            theme_color=user_theme_color(int(link.requester_id)),
            theme_icon=user_theme_icon(int(link.requester_id)),
            requested_at=link.created_at,
        )
        for link in incoming
    ]
    incoming_items.sort(key=lambda x: x.requested_at.timestamp() if x.requested_at else 0, reverse=True)

    outgoing_items = [
        FriendsListItemOut(
            kind="outgoing",
            id=int(link.addressee_id),
            username=user_username(int(link.addressee_id)),
            avatar_name=user_avatar_name(int(link.addressee_id)),
            role=user_role(int(link.addressee_id)),
            theme_color=user_theme_color(int(link.addressee_id)),
            theme_icon=user_theme_icon(int(link.addressee_id)),
            requested_at=link.created_at,
        )
        for link in outgoing
    ]
    outgoing_items.sort(key=lambda x: x.requested_at.timestamp() if x.requested_at else 0, reverse=True)

    return FriendsListOut(items=[*incoming_items, *online_items, *offline_items, *outgoing_items])


@router.get("/incoming_count", response_model=FriendIncomingCountOut)
@log_route("friends.incoming_count")
@rate_limited(lambda ident, **_: f"rl:friends:incoming_count:{ident['id']}", limit=10, window_s=1)
async def incoming_count(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendIncomingCountOut:
    uid = int(ident["id"])
    count = await db.scalar(
        select(func.count(FriendLink.id))
        .where(FriendLink.status == "pending", FriendLink.addressee_id == uid)
    )
    return FriendIncomingCountOut(count=int(count or 0))


@router.get("/blacklist", response_model=BlacklistOut)
@log_route("friends.blacklist.list")
@rate_limited(lambda ident, **_: f"rl:friends:blacklist:list:{ident['id']}", limit=10, window_s=1)
async def blacklist_list(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> BlacklistOut:
    uid = int(ident["id"])
    if not await user_has_active_subscription(db, uid):
        await clear_user_blacklist(db, uid)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="subscription_required")

    items = await build_blacklist_items(db, uid)
    return BlacklistOut(items=[BlacklistItemOut(**item) for item in items])


@router.post("/blacklist/{user_id}", response_model=Ok)
@log_route("friends.blacklist.add")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:blacklist:add:{ident['id']}:{user_id}", limit=5, window_s=5)
async def blacklist_add(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(user_id)
    created, _affected_friend_ids = await add_user_to_blacklist(db, owner_id=uid, target_id=target_id)
    if created:
        target_profile = await get_user_profile_cached(db, target_id)
        await log_action(
            db,
            user_id=uid,
            username=ident["username"],
            action="blacklist_added",
            details=(
                f"blacklist_added target_user={target_id} "
                f"target_username={(target_profile or {}).get('username') or f'user{target_id}'}"
            ),
        )
    return Ok()


@router.delete("/blacklist/{user_id}", response_model=Ok)
@log_route("friends.blacklist.remove")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:blacklist:remove:{ident['id']}:{user_id}", limit=5, window_s=5)
async def blacklist_remove(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(user_id)
    removed = await remove_user_from_blacklist(db, owner_id=uid, target_id=target_id)
    if removed:
        target_profile = await get_user_profile_cached(db, target_id)
        await log_action(
            db,
            user_id=uid,
            username=ident["username"],
            action="blacklist_removed",
            details=(
                f"blacklist_removed target_user={target_id} "
                f"target_username={(target_profile or {}).get('username') or f'user{target_id}'}"
            ),
        )
    return Ok()


@router.post("/requests/{user_id}", response_model=Ok)
@log_route("friends.request_send")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:request:{ident['id']}:{user_id}", limit=3, window_s=5)
async def send_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(user_id)
    if target_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if target_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    target = await db.scalar(
        select(User)
        .where(User.id == target_id)
        .with_for_update()
    )
    if not target or target.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if not bool(target.allow_friend_requests):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="target_friend_requests_disabled",
        )

    if normalize_user_role(ident.get("role")) == ROLE_ADMIN or normalize_user_role(target.role) == ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_friend_requests_disabled")

    await raise_if_friend_request_blocked_by_blacklist(db, requester_id=uid, target_id=target_id)

    requester_profile = await get_user_profile_cached(db, uid)

    existing = await load_link(db, uid, target_id)
    if existing:
        if existing.status == "accepted":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_friends")

        if int(existing.requester_id) == uid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="request_already_sent")

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="incoming_request")

    link = FriendLink(requester_id=uid, addressee_id=target_id, status="pending")
    db.add(link)
    await db.commit()
    await db.refresh(link)

    title = "Заявка в друзья от"
    text = f"Пользователь {ident['username']} отправил вам заявку в друзья."

    actions = [
        {"kind": "api", "label": "Принять", "url": f"/friends/requests/{uid}/accept", "method": "post", "style": "primary"},
        {"kind": "api", "label": "Отклонить", "url": f"/friends/requests/{uid}/decline", "method": "post", "style": "neutral"},
    ]
    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "title": title,
                "text": text,
                "date": datetime.now(timezone.utc).isoformat(),
                "kind": "friend_request",
                "ttl_ms": 15000,
                "read": False,
                "user": {
                    "id": uid,
                    "username": ident["username"],
                    "avatar_name": (requester_profile or {}).get("avatar_name"),
                    "role": (requester_profile or {}).get("role"),
                    "theme_color": (requester_profile or {}).get("theme_color"),
                    "theme_icon": (requester_profile or {}).get("theme_icon"),
                },
                "actions": actions,
                "toast_text": "",
            },
            room=f"user:{target_id}",
            namespace="/auth",
        )
    await emit_friends_update(target_id, uid, "incoming")
    await emit_friends_update(uid, target_id, "outgoing")

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_sent",
        details=(
            f"friend_request_sent target_user={target_id} "
            f"target_username={target.username or f'user{target_id}'}"
        ),
    )

    return Ok()


@router.post("/requests/{user_id}/accept", response_model=Ok)
@log_route("friends.request_accept")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:accept:{ident['id']}:{user_id}", limit=5, window_s=5)
async def accept_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    requester_id = int(user_id)
    if requester_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if requester_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    upd = await db.execute(
        update(FriendLink)
        .where(FriendLink.requester_id == requester_id, FriendLink.addressee_id == uid, FriendLink.status == "pending")
        .values(status="accepted", responded_at=func.now())
    )
    if int(upd.rowcount or 0) <= 0:
        await raise_missing_incoming_request_error(db, uid, requester_id)

    await db.commit()

    requester_profile = await get_user_profile_cached(db, requester_id)
    requester_name = cast(str | None, (requester_profile or {}).get("username"))
    accepter_profile = await get_user_profile_cached(db, uid)

    title_req = "Заявка в друзья принята"
    text_req = f"Пользователь {ident['username']} принял вашу заявку в друзья."
    with suppress(Exception):
        await sio.emit(
            "notify",
            {
                "title": title_req,
                "text": text_req,
                "date": datetime.now(timezone.utc).isoformat(),
                "kind": "friend_accept",
                "ttl_ms": 15000,
                "read": False,
                "user": {
                    "id": uid,
                    "username": ident["username"],
                    "avatar_name": (accepter_profile or {}).get("avatar_name"),
                    "role": (accepter_profile or {}).get("role"),
                    "theme_color": (accepter_profile or {}).get("theme_color"),
                    "theme_icon": (accepter_profile or {}).get("theme_icon"),
                },
                "toast_text": "",
            },
            room=f"user:{requester_id}",
            namespace="/auth",
        )

    await emit_friends_update(requester_id, uid, "friends")
    await emit_friends_update(uid, requester_id, "friends")

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_accepted",
        details=(
            f"friend_request_accepted requester_user={requester_id} "
            f"requester_username={requester_name or f'user{requester_id}'}"
        ),
    )

    return Ok()


@router.post("/requests/{user_id}/decline", response_model=Ok)
@log_route("friends.request_decline")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:decline:{ident['id']}:{user_id}", limit=5, window_s=5)
async def decline_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    requester_id = int(user_id)
    if requester_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if requester_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    deleted = await db.execute(
        delete(FriendLink).where(
            FriendLink.requester_id == requester_id,
            FriendLink.addressee_id == uid,
            FriendLink.status == "pending",
        )
    )
    if int(deleted.rowcount or 0) <= 0:
        await raise_missing_incoming_request_error(db, uid, requester_id)

    await db.commit()
    await emit_friends_update(requester_id, uid, "none")
    await emit_friends_update(uid, requester_id, "none")
    requester_profile = await get_user_profile_cached(db, requester_id)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_declined",
        details=(
            f"friend_request_declined requester_user={requester_id} "
            f"requester_username={(requester_profile or {}).get('username') or f'user{requester_id}'}"
        ),
    )

    return Ok()


@router.delete("/requests/{user_id}", response_model=Ok)
@log_route("friends.request_cancel")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:cancel:{ident['id']}:{user_id}", limit=5, window_s=5)
async def cancel_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(user_id)
    if target_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if target_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    link = await load_link(db, uid, target_id)
    if not link or link.status != "pending" or int(link.requester_id) != uid:
        await raise_missing_outgoing_request_error(db, uid, target_id)

    request_seconds = elapsed_seconds_since(cast(datetime | None, link.created_at))
    if request_seconds is not None and request_seconds < FRIEND_REMOVE_MIN_SECONDS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="friend_request_cancel_too_early")

    deleted = await db.execute(
        delete(FriendLink).where(
            FriendLink.id == link.id,
            FriendLink.requester_id == uid,
            FriendLink.addressee_id == target_id,
            FriendLink.status == "pending",
        )
    )
    if int(deleted.rowcount or 0) <= 0:
        await raise_missing_outgoing_request_error(db, uid, target_id)

    await db.commit()
    await emit_friends_update(target_id, uid, "none")
    await emit_friends_update(uid, target_id, "none")
    target_profile = await get_user_profile_cached(db, target_id)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_canceled",
        details=(
            f"friend_request_canceled target_user={target_id} "
            f"target_username={(target_profile or {}).get('username') or f'user{target_id}'}"
        ),
    )

    return Ok()


@router.delete("/{user_id}", response_model=Ok)
@log_route("friends.remove")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:remove:{ident['id']}:{user_id}", limit=5, window_s=5)
async def remove_friend(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    other_id = int(user_id)
    if other_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if other_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_remove")

    link = await load_link(db, uid, other_id)
    if not link or link.status != "accepted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="friend_not_found")

    responded_at = cast(datetime | None, link.responded_at)
    created_at = cast(datetime | None, link.created_at)
    accepted_at = responded_at or created_at
    friendship_seconds = elapsed_seconds_since(accepted_at)
    if friendship_seconds is not None and friendship_seconds < FRIEND_REMOVE_MIN_SECONDS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="friend_remove_too_early")

    await db.execute(delete(FriendLink).where(FriendLink.id == link.id))
    await db.commit()
    await emit_friends_update(other_id, uid, "none")
    await emit_friends_update(uid, other_id, "none")
    other_profile = await get_user_profile_cached(db, other_id)

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_removed",
        details=(
            f"friend_removed target_user={other_id} "
            f"target_username={(other_profile or {}).get('username') or f'user{other_id}'}"
        ),
    )

    return Ok()


@router.post("/invite", response_model=Ok)
@log_route("friends.invite")
@rate_limited(lambda ident, **_: f"rl:friends:invite:{ident['id']}", limit=5, window_s=5)
async def invite_friend(payload: FriendInviteIn, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(payload.user_id)
    room_id = int(payload.room_id)
    if target_id <= 0 or room_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_payload")

    if target_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_invite")

    link = await load_link(db, uid, target_id)
    if not link or link.status != "accepted":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_friends")

    r = get_redis()
    params = await get_room_params_or_404(r, room_id)
    room_title = str(params.get("title") or f"Комната #{room_id}")

    target = await db.get(User, target_id)
    if not target or target.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    target_active_sanctions = await fetch_active_sanctions(db, target_id)
    if target_active_sanctions.get(SANCTION_BAN):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_banned")

    if target_active_sanctions.get(SANCTION_TIMEOUT):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_timeout")

    base_online_ids = set(await fetch_online_user_ids(r))
    online_ids = await fetch_effective_online_user_ids(r, [target_id], base_online_ids=base_online_ids)
    target_online = target_id in online_ids

    target_active_head_room_by_uid = await active_game_head_room_by_uid(r, [target_id])
    if target_active_head_room_by_uid.get(target_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_in_active_game_as_host")

    if not target_online:
        if not target.telegram_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_not_verified")

        if not bool(target.tg_invites_enabled):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_invites_disabled")

    if target_online:
        try:
            target_active_game_room_id = int(await r.get(active_alive_game_room_key(target_id)) or 0)
        except Exception:
            target_active_game_room_id = 0
        if target_active_game_room_id > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_in_active_game_as_alive_player")

    invite_set_key = f"room:{room_id}:invited"
    tg_cooldown_key = tg_room_invite_cooldown_key(target_id)
    tg_cooldown_reserved = False
    in_room_now = bool(await r.sismember(f"room:{room_id}:members", str(target_id)))
    if not in_room_now:
        in_room_now = bool(await r.sismember(f"room:{room_id}:spectators", str(target_id)))
    if in_room_now:
        with suppress(Exception):
            await r.srem(invite_set_key, str(target_id))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_already_in_room")

    if not target_online:
        tg_cooldown_reserved = bool(await r.set(tg_cooldown_key, str(int(time())), nx=True, ex=TG_ROOM_INVITE_COOLDOWN_S))
        if not tg_cooldown_reserved:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_invite_cooldown_active")

    invite_reserved = bool(await r.sadd(invite_set_key, str(target_id)))
    if not invite_reserved:
        if tg_cooldown_reserved:
            with suppress(Exception):
                await r.delete(tg_cooldown_key)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="room_invite_already_sent")

    is_private = str(params.get("privacy") or "open").strip() == "private"
    is_owner_invite = int(params.get("creator") or 0) == uid
    auto_allowed = False
    inviter_profile = await get_user_profile_cached(db, uid)
    inviter_name = str(ident.get("username") or (inviter_profile or {}).get("username") or f"user{uid}")

    if target_online:
        title = "Приглашение в комнату"
        text = f"{inviter_name} приглашает Вас в «{room_title}»."
        note = Notif(user_id=target_id, title=title, text=text)
        db.add(note)
        await db.commit()
        await db.refresh(note)

        await emit_notify(
            target_id,
            note,
            kind="room_invite",
            extra={
                "action": {"kind": "route", "label": "Перейти", "to": f"/room/{room_id}"},
                "room_id": room_id,
                "user": {
                    "id": uid,
                    "username": inviter_name,
                    "avatar_name": (inviter_profile or {}).get("avatar_name"),
                    "role": (inviter_profile or {}).get("role"),
                    "theme_color": (inviter_profile or {}).get("theme_color"),
                    "theme_icon": (inviter_profile or {}).get("theme_icon"),
                },
                "toast_title": "Приглашение в комнату от",
                "toast_text": "",
            },
        )
    else:
        room_url = f"https://{settings.DOMAIN}/room/{room_id}"
        tg_text = f"{inviter_name} приглашает Вас в «{room_title}»\n{room_url}\n\nПриглашения можно отключить в Личном кабинете\nhttps://deceit.games/profile"
        send_result = await send_text_message(chat_id=int(target.telegram_id or 0), text=tg_text)
        if not send_result.ok:
            if send_result.reason == "telegram_chat_unavailable":
                with suppress(Exception):
                    await r.srem(invite_set_key, str(target_id))
                with suppress(Exception):
                    await r.delete(tg_cooldown_key)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_unreachable")

            with suppress(Exception):
                await r.srem(invite_set_key, str(target_id))
            with suppress(Exception):
                await r.delete(tg_cooldown_key)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="telegram_unavailable")

    if is_private and is_owner_invite:
        async with r.pipeline(transaction=True) as p:
            await p.srem(f"room:{room_id}:pending", str(target_id))
            await p.sadd(f"room:{room_id}:allow", str(target_id))
            await p.zadd(f"room:{room_id}:requests", {str(target_id): int(time())}, nx=True)
            res = await p.execute()
        auto_allowed = int(res[1] or 0) > 0

    if auto_allowed:
        with suppress(Exception):
            await emit_rooms_upsert(room_id)
            await sio.emit(
                "room_app_approved",
                {
                    "room_id": room_id,
                    "user_id": target_id,
                    "silent_unread": True,
                    "source": "owner_invite_auto_approved",
                },
                room=f"user:{uid}",
                namespace="/auth",
            )

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_room_invite",
        details=(
            f"friend_room_invite target_user={target_id} "
            f"target_username={target.username or f'user{target_id}'} "
            f"room_id={room_id} "
            f"channel={'site' if target_online else 'telegram'} auto_allowed={int(auto_allowed)}"
        ),
    )

    return Ok()
