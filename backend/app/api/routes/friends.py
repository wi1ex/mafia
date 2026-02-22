from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timezone
from time import time
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, delete, update, func, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.settings import settings
from ...core.clients import get_redis
from ...core.logging import log_action
from ...models.friend import FriendLink, FriendCloseness
from ...models.user import User
from ...models.notif import Notif
from ...realtime.utils import get_rooms_brief
from ...realtime.sio import sio
from ...services.telegram import send_text_message
from ...services.user_cache import get_user_profile_cached
from ...schemas.common import Identity, Ok
from ...schemas.friend import FriendStatusOut, FriendsListOut, FriendsListItemOut, FriendIncomingCountOut, FriendInviteIn
from ...schemas.room import RoomBriefOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...api.utils import (
    emit_rooms_upsert,
    fetch_online_user_ids,
    fetch_effective_online_user_ids,
    get_room_params_or_404,
    pair,
    load_link,
    emit_notify,
    emit_friends_update,
)

router = APIRouter()


@log_route("friends.status")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:status:{ident['id']}:{user_id}", limit=10, window_s=1)
@router.get("/status/{user_id}", response_model=FriendStatusOut)
async def friend_status(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendStatusOut:
    uid = int(ident["id"])
    if user_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if user_id == uid:
        return FriendStatusOut(status="self")

    link = await load_link(db, uid, int(user_id))
    if not link:
        return FriendStatusOut(status="none")

    if link.status == "accepted":
        return FriendStatusOut(status="friends")

    if link.requester_id == uid:
        return FriendStatusOut(status="outgoing")

    return FriendStatusOut(status="incoming")


@log_route("friends.list")
@rate_limited(lambda ident, **_: f"rl:friends:list:{ident['id']}", limit=10, window_s=1)
@router.get("/list", response_model=FriendsListOut)
async def friends_list(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendsListOut:
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

    all_ids = set(friend_ids + incoming_ids + outgoing_ids)
    users_map: dict[int, dict[str, object]] = {}
    if all_ids:
        rows = await db.execute(
            select(
                User.id,
                User.username,
                User.avatar_name,
                User.telegram_id,
                User.tg_invites_enabled,
            ).where(User.id.in_(all_ids))
        )
        for rid, username, avatar_name, telegram_id, tg_invites_enabled in rows.all():
            uid_i = int(rid)
            users_map[uid_i] = {
                "username": username,
                "avatar_name": avatar_name,
                "telegram_verified": bool(telegram_id),
                "tg_invites_enabled": bool(tg_invites_enabled),
            }

    closeness_map: dict[tuple[int, int], int] = {}
    if friend_ids:
        pairs = [pair(uid, fid) for fid in friend_ids]
        if pairs:
            rows = await db.execute(
                select(FriendCloseness.user_low, FriendCloseness.user_high, FriendCloseness.games_together)
                .where(tuple_(FriendCloseness.user_low, FriendCloseness.user_high).in_(pairs))
            )
            for lo, hi, games in rows.all():
                closeness_map[(int(lo), int(hi))] = int(games or 0)

    room_by_uid: dict[int, int] = {}
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
                room_by_uid[int(fid)] = rid

    rooms_map: dict[int, RoomBriefOut] = {}
    room_ids = list({rid for rid in room_by_uid.values() if rid > 0})
    if room_ids:
        items = await get_rooms_brief(r, room_ids)
        for item in items:
            try:
                out = RoomBriefOut(**item)
                rooms_map[int(out.id)] = out
            except Exception:
                continue

    def user_username(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("username")
        return str(raw) if isinstance(raw, str) else None

    def user_avatar_name(user_id: int) -> str | None:
        raw = (users_map.get(user_id) or {}).get("avatar_name")
        return str(raw) if isinstance(raw, str) else None

    def build_friend_item(fid: int) -> FriendsListItemOut:
        user_data = users_map.get(fid) or {}
        name = user_username(fid)
        avatar = user_avatar_name(fid)
        online = fid in online_ids
        closeness = closeness_map.get(pair(uid, fid), 0)
        rid = room_by_uid.get(fid) if online else None
        info = rooms_map.get(int(rid)) if rid else None
        return FriendsListItemOut(
            kind="online" if online else "offline",
            id=int(fid),
            username=name,
            avatar_name=avatar,
            online=online,
            closeness=closeness,
            room_id=int(rid) if rid else None,
            room_title=info.title if info else None,
            room_in_game=bool(info.in_game) if info else None,
            telegram_verified=bool(user_data.get("telegram_verified")),
            tg_invites_enabled=bool(user_data.get("tg_invites_enabled")),
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
            requested_at=link.created_at,
        )
        for link in outgoing
    ]
    outgoing_items.sort(key=lambda x: x.requested_at.timestamp() if x.requested_at else 0, reverse=True)

    return FriendsListOut(items=[*incoming_items, *online_items, *offline_items, *outgoing_items])


@log_route("friends.incoming_count")
@rate_limited(lambda ident, **_: f"rl:friends:incoming_count:{ident['id']}", limit=10, window_s=1)
@router.get("/incoming_count", response_model=FriendIncomingCountOut)
async def incoming_count(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendIncomingCountOut:
    uid = int(ident["id"])
    count = await db.scalar(
        select(func.count(FriendLink.id))
        .where(FriendLink.status == "pending", FriendLink.addressee_id == uid)
    )
    return FriendIncomingCountOut(count=int(count or 0))


@log_route("friends.request_send")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:request:{ident['id']}:{user_id}", limit=3, window_s=5)
@router.post("/requests/{user_id}", response_model=Ok)
async def send_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    target_id = int(user_id)
    if target_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if target_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    target = await db.get(User, target_id)
    if not target or target.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

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

    title = "Заявка в друзья"
    text = f"Пользователь {ident['username']} отправил вам заявку в друзья."
    note = Notif(user_id=target_id, title=title, text=text)
    db.add(note)
    await db.commit()
    await db.refresh(note)

    actions = [
        {"kind": "api", "label": "Принять", "url": f"/friends/requests/{uid}/accept", "method": "post", "style": "primary"},
        {"kind": "api", "label": "Отклонить", "url": f"/friends/requests/{uid}/decline", "method": "post", "style": "danger"},
    ]
    await emit_notify(
        target_id,
        note,
        kind="friend_request",
        extra={
            "user": {"id": uid, "username": ident["username"], "avatar_name": (requester_profile or {}).get("avatar_name")},
            "actions": actions,
            "toast_text": "",
        },
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


@log_route("friends.request_accept")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:accept:{ident['id']}:{user_id}", limit=5, window_s=5)
@router.post("/requests/{user_id}/accept", response_model=Ok)
async def accept_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    requester_id = int(user_id)
    if requester_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if requester_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    link = await db.scalar(
        select(FriendLink).where(
            FriendLink.requester_id == requester_id,
            FriendLink.addressee_id == uid,
            FriendLink.status == "pending",
        ).limit(1)
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_not_found")

    await db.execute(
        update(FriendLink)
        .where(FriendLink.id == link.id)
        .values(status="accepted", responded_at=func.now())
    )
    await db.commit()

    requester_profile = await get_user_profile_cached(db, requester_id)
    requester_name = cast(str | None, (requester_profile or {}).get("username"))
    accepter_profile = await get_user_profile_cached(db, uid)

    title_req = "Заявка в друзья принята"
    text_req = f"Пользователь {ident['username']} принял вашу заявку в друзья."
    note_req = Notif(user_id=requester_id, title=title_req, text=text_req)
    db.add(note_req)
    await db.commit()
    await db.refresh(note_req)
    await emit_notify(
        requester_id,
        note_req,
        kind="friend_accept",
        extra={
            "user": {"id": uid, "username": ident["username"], "avatar_name": (accepter_profile or {}).get("avatar_name")},
            "toast_text": "",
        },
    )

    title_acc = "Добавлен в друзья"
    text_acc = f"Вы приняли заявку в друзья от пользователя {requester_name or f'user{requester_id}'}."
    note_acc = Notif(
        user_id=uid,
        title=title_acc,
        text=text_acc,
        read_at=datetime.now(timezone.utc),
    )
    db.add(note_acc)
    await db.commit()
    await db.refresh(note_acc)
    await emit_notify(uid, note_acc, kind="friend_accept", no_toast=True)
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


@log_route("friends.request_decline")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:decline:{ident['id']}:{user_id}", limit=5, window_s=5)
@router.post("/requests/{user_id}/decline", response_model=Ok)
async def decline_friend_request(user_id: int, ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> Ok:
    uid = int(ident["id"])
    requester_id = int(user_id)
    if requester_id <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad_user_id")

    if requester_id == uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="self_request")

    link = await db.scalar(
        select(FriendLink).where(
            FriendLink.requester_id == requester_id,
            FriendLink.addressee_id == uid,
            FriendLink.status == "pending",
        ).limit(1)
    )
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="request_not_found")

    await db.execute(delete(FriendLink).where(FriendLink.id == link.id))
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


@log_route("friends.remove")
@rate_limited(lambda ident, user_id, **_: f"rl:friends:remove:{ident['id']}:{user_id}", limit=5, window_s=5)
@router.delete("/{user_id}", response_model=Ok)
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


@log_route("friends.invite")
@rate_limited(lambda ident, **_: f"rl:friends:invite:{ident['id']}", limit=5, window_s=5)
@router.post("/invite", response_model=Ok)
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

    base_online_ids = set(await fetch_online_user_ids(r))
    online_ids = await fetch_effective_online_user_ids(r, [target_id], base_online_ids=base_online_ids)
    target_online = target_id in online_ids
    if not target_online:
        if not target.telegram_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_not_verified")

        if not bool(target.tg_invites_enabled):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_invites_disabled")

    cooldown_key = f"friends:invite:cooldown:{uid}:{target_id}:{room_id}"
    retry_after = int(await r.ttl(cooldown_key) or 0)
    if retry_after > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="invite_cooldown",
            headers={"Retry-After": str(retry_after)},
        )

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
                },
                "toast_title": "Приглашение в комнату от",
                "toast_text": "",
            },
        )
    else:
        room_url = f"https://{settings.DOMAIN}/room/{room_id}"
        tg_text = f"**{inviter_name}** приглашает Вас в «**{room_title}**»\n{room_url}\n\nУведомления можно отключить в Личном кабинете\nhttps://deceit.games/profile"
        send_result = await send_text_message(chat_id=int(target.telegram_id or 0), text=tg_text)
        if not send_result.ok:
            if send_result.reason == "telegram_chat_unavailable":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target_telegram_unreachable")

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
    await r.set(cooldown_key, "1", ex=30 * 60)

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
