from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, delete, update, func, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.clients import get_redis
from ...core.logging import log_action
from ...core.settings import settings
from ...models.friend import FriendLink, FriendCloseness
from ...models.user import User
from ...models.notif import Notif
from ...realtime.utils import get_rooms_brief
from ...schemas.common import Identity, Ok
from ...schemas.friend import FriendStatusOut, FriendsListOut, FriendItemOut, FriendRequestOut, FriendInviteIn
from ...schemas.room import RoomBriefOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...api.utils import fetch_online_user_ids, get_room_params_or_404, pair, load_link, emit_notify, emit_friends_update
from ...services.telegram import send_telegram_message

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
@rate_limited(lambda ident, **_: f"rl:friends:list:{ident['id']}", limit=5, window_s=1)
@router.get("/list", response_model=FriendsListOut)
async def friends_list(ident: Identity = Depends(get_identity), db: AsyncSession = Depends(get_session)) -> FriendsListOut:
    uid = int(ident["id"])
    accepted_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "accepted", or_(FriendLink.requester_id == uid, FriendLink.addressee_id == uid))
    )
    incoming_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "pending", FriendLink.addressee_id == uid)
    )
    outgoing_rows = await db.execute(
        select(FriendLink)
        .where(FriendLink.status == "pending", FriendLink.requester_id == uid)
    )

    accepted = accepted_rows.scalars().all()
    incoming = incoming_rows.scalars().all()
    outgoing = outgoing_rows.scalars().all()

    friend_ids: list[int] = []
    for link in accepted:
        friend_ids.append(int(link.addressee_id if link.requester_id == uid else link.requester_id))

    incoming_ids = [int(x.requester_id) for x in incoming]
    outgoing_ids = [int(x.addressee_id) for x in outgoing]

    all_ids = set(friend_ids + incoming_ids + outgoing_ids)
    users_map: dict[int, tuple[str | None, str | None]] = {}
    if all_ids:
        rows = await db.execute(select(User.id, User.username, User.avatar_name).where(User.id.in_(all_ids)))
        for rid, username, avatar_name in rows.all():
            users_map[int(rid)] = (username, avatar_name)

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

    r = get_redis()
    online_ids = set(await fetch_online_user_ids(r))

    room_by_uid: dict[int, int] = {}
    if friend_ids:
        async with r.pipeline() as p:
            for fid in friend_ids:
                await p.get(f"user:{int(fid)}:room")
            raw_rooms = await p.execute()
        for fid, raw in zip(friend_ids, raw_rooms):
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

    def build_friend_item(fid: int) -> FriendItemOut:
        name, avatar = users_map.get(fid, (None, None))
        online = fid in online_ids
        closeness = closeness_map.get(pair(uid, fid), 0)
        rid = room_by_uid.get(fid)
        info = rooms_map.get(int(rid)) if rid else None
        return FriendItemOut(
            id=int(fid),
            username=name,
            avatar_name=avatar,
            online=online,
            closeness=closeness,
            room_id=int(rid) if rid else None,
            room_title=info.title if info else None,
            room_in_game=bool(info.in_game) if info else None,
        )

    friends_items = [build_friend_item(fid) for fid in friend_ids]
    friends_items.sort(key=lambda x: (-x.closeness, (x.username or f"user{x.id}").lower()))

    online_items = [f for f in friends_items if f.online]
    offline_items = [f for f in friends_items if not f.online]

    incoming_items = [
        FriendRequestOut(
            id=int(link.requester_id),
            username=users_map.get(int(link.requester_id), (None, None))[0],
            avatar_name=users_map.get(int(link.requester_id), (None, None))[1],
            requested_at=link.created_at,
        )
        for link in incoming
    ]
    outgoing_items = [
        FriendRequestOut(
            id=int(link.addressee_id),
            username=users_map.get(int(link.addressee_id), (None, None))[0],
            avatar_name=users_map.get(int(link.addressee_id), (None, None))[1],
            requested_at=link.created_at,
        )
        for link in outgoing
    ]

    return FriendsListOut(
        online=online_items,
        offline=offline_items,
        incoming=incoming_items,
        outgoing=outgoing_items,
    )


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
        extra={"user": {"id": uid, "username": ident["username"]}, "actions": actions, "toast_text": ""},
    )
    await emit_friends_update(target_id, uid, "incoming")
    await emit_friends_update(uid, target_id, "outgoing")

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_sent",
        details=f"friend_request_sent target_user={target_id}",
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

    requester = await db.get(User, requester_id)
    requester_name = requester.username if requester else None

    title_req = "Заявка в друзья принята"
    text_req = f"Пользователь {ident['username']} принял вашу заявку в друзья."
    note_req = Notif(user_id=requester_id, title=title_req, text=text_req)
    db.add(note_req)
    await db.commit()
    await db.refresh(note_req)
    await emit_notify(requester_id, note_req, kind="friend_accept")

    title_acc = "Добавлен в друзья"
    text_acc = f"Вы приняли заявку в друзья от пользователя {requester_name or f'user{requester_id}'}."
    note_acc = Notif(user_id=uid, title=title_acc, text=text_acc)
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
        details=f"friend_request_accepted requester_user={requester_id}",
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

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_request_declined",
        details=f"friend_request_declined requester_user={requester_id}",
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

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_removed",
        details=f"friend_removed target_user={other_id}",
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

    title = "Приглашение в комнату"
    text = f"Пользователь {ident['username']} приглашает вас в комнату «{room_title}»."
    note = Notif(user_id=target_id, title=title, text=text)
    db.add(note)
    await db.commit()
    await db.refresh(note)

    online_ids = set(await fetch_online_user_ids(r))
    is_online = target_id in online_ids
    if is_online:
        await emit_notify(
            target_id,
            note,
            kind="room_invite",
            extra={
                "action": {"kind": "route", "label": "Перейти", "to": f"/room/{room_id}"},
                "room_id": room_id,
                "user": {"id": uid, "username": ident["username"]},
            },
        )
    else:
        link_url = f"https://{settings.DOMAIN}/room/{room_id}"
        if target.telegram_id:
            await send_telegram_message(
                int(target.telegram_id),
                f"{ident['username']} приглашает вас в комнату «{room_title}».\n{link_url}",
            )

    await log_action(
        db,
        user_id=uid,
        username=ident["username"],
        action="friend_room_invite",
        details=f"friend_room_invite target_user={target_id} room_id={room_id}",
    )

    return Ok()
