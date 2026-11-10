from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import structlog
from fastapi import HTTPException
from sqlalchemy import String, and_, cast, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import SessionLocal
from ..core.logging import log_action
from ..core.roles import ROLE_ADMIN, ROLE_MODER, normalize_user_role
from ..core.settings import settings
from ..models.gift import Gift, UserGift
from ..models.notif import Notif
from ..models.user import User
from ..schemas.gifts import (
    GiftMoveIn, GiftPurchaseIn, GiftPurchaseOut, GiftRemovalOut, GiftRemovalQuoteOut,
    GiftSenderOut, UserGiftOut, UserGiftsOut,
)
from .blacklist import blacklist_relation
from .user_cache import UserProfile, get_user_profiles_cached
from .wallet import (
    _persist_notice_once,
    adjust_dc_balance,
    checked_balance,
    ensure_gift_recipient_access,
    ensure_payments_enabled,
    ensure_purchase_access,
    get_dc_balance,
    lock_dc_request,
    lock_user_balance,
)

if TYPE_CHECKING:
    from ..api.utils import ToastFields

log = structlog.get_logger()
_GIFT_EVENT_KEY_PREFIX = "dc:gift:"
_GIFT_OWNER_EVENT_KEY_SUFFIX = ":owner"


async def gift_catalog(session: AsyncSession) -> list[Gift]:
    rows = await session.scalars(
        select(Gift).where(Gift.visible.is_(True), Gift.deleted_at.is_(None))
        .order_by(Gift.price_dc, Gift.id)
    )
    return list(rows.all())


def _purchase_result(acquisition: UserGift, dc_balance: int) -> GiftPurchaseOut:
    return GiftPurchaseOut(
        purchase_id=acquisition.id,
        gift_id=acquisition.gift_id,
        recipient_id=acquisition.owner_id,
        recipient_username=acquisition.owner_username,
        dc_balance=dc_balance,
    )


async def buy_gift(session: AsyncSession, *, payer_id: int, payload: GiftPurchaseIn) -> GiftPurchaseOut:
    owner_id = payload.recipient_id if payload.recipient_id is not None else payer_id
    if payload.recipient_id == payer_id:
        raise HTTPException(422, detail="gift_self_not_allowed")

    if payload.anonymous and owner_id == payer_id:
        raise HTTPException(422, detail="gift_anonymous_requires_recipient")

    request_id = str(payload.request_id)
    await lock_dc_request(session, request_id, journal="gift")
    existing = await session.scalar(select(UserGift).where(UserGift.request_id == request_id))
    if existing is not None:
        if (existing.payer_id != payer_id or existing.owner_id != owner_id
                or existing.gift_id != payload.gift_id or existing.anonymous != payload.anonymous
                or existing.dc_cost != payload.expected_dc_cost):
            raise HTTPException(409, detail="idempotency_conflict")

        payer = await lock_user_balance(session, payer_id)
        result = _purchase_result(existing, payer.dc_balance)
        await session.commit()
        return result

    gift = await session.scalar(
        select(Gift).where(Gift.id == payload.gift_id).with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if gift is None:
        raise HTTPException(404, detail="gift_not_found")

    if gift.deleted_at is not None or not gift.visible:
        raise HTTPException(409, detail="gift_unavailable")

    if gift.price_dc != payload.expected_dc_cost:
        raise HTTPException(409, detail={"code": "gift_price_changed", "price_dc": gift.price_dc})

    users = {}
    for uid in sorted({payer_id, owner_id}):
        try:
            users[uid] = await lock_user_balance(session, uid)
        except HTTPException as exc:
            if uid == owner_id and owner_id != payer_id and exc.status_code == 404:
                raise HTTPException(404, detail="gift_recipient_not_found") from None

            raise

    payer, owner = users[payer_id], users[owner_id]
    await ensure_payments_enabled(session)
    await ensure_purchase_access(session, payer)
    if payer_id != owner_id:
        await ensure_gift_recipient_access(session, owner)
        payer_role = normalize_user_role(payer.role)
        if normalize_user_role(owner.role) == ROLE_ADMIN and payer_role != ROLE_ADMIN:
            raise HTTPException(404, detail="gift_recipient_not_found")

        relation = await blacklist_relation(session, payer_id, owner_id)
        if relation["a_blocks_b"] or (relation["b_blocks_a"] and payer_role not in {ROLE_ADMIN, ROLE_MODER}):
            raise HTTPException(403, detail="gift_recipient_blacklisted")

    balance_before = int(payer.dc_balance)
    payer.dc_balance = checked_balance(balance_before, -gift.price_dc)
    acquisition = UserGift(
        gift_id=gift.id, owner_id=owner_id, payer_id=payer_id,
        payer_username=payer.username, owner_username=owner.username,
        anonymous=payload.anonymous, dc_cost=gift.price_dc, request_id=request_id,
        toast_pending=owner_id != payer_id,
        acquired_at=datetime.now(timezone.utc), balance_before=balance_before, balance_after=payer.dc_balance,
    )
    session.add(acquisition)
    await session.flush()
    result = _purchase_result(acquisition, payer.dc_balance)
    owner_note, payer_note = await _persist_gift_notices(session, acquisition)
    await log_action(
        session,
        user_id=payer_id,
        username=acquisition.payer_username,
        action="gift_sent" if payer_id != owner_id else "gift_purchase",
        details=(
            f"purchase_id={acquisition.id} gift_id={acquisition.gift_id} dc_cost={acquisition.dc_cost} "
            f"recipient_id={owner_id} recipient_username={acquisition.owner_username} anonymous={int(acquisition.anonymous)}"
        ),
        commit=False,
    )
    await session.commit()

    await _notify_gift_purchase(acquisition, owner_note=owner_note, payer_note=payer_note)
    await _publish_gift_changes({owner_id, payer_id}, {payer_id})
    return result


async def _persist_gift_notices(session: AsyncSession, acquisition: UserGift) -> tuple[Notif | None, Notif | None]:
    payment = f"Списано: {acquisition.dc_cost} DC. Баланс: {acquisition.balance_after} DC."
    event_key = f"{_GIFT_EVENT_KEY_PREFIX}{acquisition.id}"
    owner_event_key = event_key + _GIFT_OWNER_EVENT_KEY_SUFFIX
    if acquisition.payer_id == acquisition.owner_id:
        note = await _persist_notice_once(
            session, user_id=acquisition.owner_id, event_key=owner_event_key,
            title="Покупка подарка", text=f"Вы купили подарок. {payment}",
        )
        return note, None

    owner_text = "Вы получили анонимный подарок."
    if not acquisition.anonymous:
        owner_text = f"{acquisition.payer_username} подарил вам подарок."
    owner_note = await _persist_notice_once(
        session, user_id=acquisition.owner_id, event_key=owner_event_key,
        title="Вам подарили подарок", text=owner_text,
    )
    sent = "Вы анонимно отправили" if acquisition.anonymous else "Вы отправили"
    payer_note = await _persist_notice_once(
        session, user_id=acquisition.payer_id, event_key=f"{event_key}:payer",
        title="Подарок отправлен", text=f"{sent} подарок пользователю {acquisition.owner_username}. {payment}",
    )
    return owner_note, payer_note


async def _sender_profiles(acquisitions: list[UserGift], *, reveal_anonymous_sender: bool = False) -> dict[int, UserProfile]:
    payer_ids = {
        row.payer_id for row in acquisitions
        if row.payer_id != row.owner_id and (reveal_anonymous_sender or not row.anonymous)
    }
    if not payer_ids:
        return {}

    try:
        async with SessionLocal() as session:
            return await get_user_profiles_cached(session, payer_ids)

    except Exception:
        log.exception("gift.sender_profiles_failed")
        return {}


def _gift_sender(acquisition: UserGift, profiles: dict[int, UserProfile], *,
                 reveal_anonymous_sender: bool = False) -> GiftSenderOut | None:
    if acquisition.payer_id == acquisition.owner_id or (acquisition.anonymous and not reveal_anonymous_sender):
        return None

    profile = profiles.get(acquisition.payer_id)
    if profile is not None and profile.get("deleted_at"):
        if not acquisition.anonymous:
            return None
        profile = None

    data = profile or {}
    return GiftSenderOut(
        id=acquisition.payer_id, username=data.get("username") or acquisition.payer_username,
        avatar_name=data.get("avatar_name"), role=data.get("role"),
        theme_color=data.get("theme_color"), theme_icon=data.get("theme_icon"),
    )


def _gift_received_toast(acquisition: UserGift, profiles: dict[int, UserProfile]) -> tuple[ToastFields, dict | None]:
    toast: ToastFields = {
        "title": "Подарок",
        "actions": [{"kind": "gift_open", "label": "Открыть", "acquisition_id": acquisition.id}],
    }
    sender = _gift_sender(acquisition, profiles)
    if acquisition.anonymous:
        toast["text"] = "Аноним отправил вам подарок"
    elif sender is not None:
        toast["text"] = ""

    return toast, {"user": sender.model_dump()} if sender is not None else None


async def _notify_gift_purchase(acquisition: UserGift, *, owner_note: Notif | None, payer_note: Notif | None) -> None:
    from ..api.utils import emit_notify

    if owner_note is not None:
        try:
            if acquisition.payer_id == acquisition.owner_id:
                await emit_notify(acquisition.owner_id, owner_note, kind="gift_purchase")
            else:
                toast, extra = _gift_received_toast(acquisition, await _sender_profiles([acquisition]))
                await emit_notify(acquisition.owner_id, owner_note, kind="gift_received", toast=toast, extra=extra)
        except Exception:
            log.exception("gift.owner_notification_failed", acquisition_id=acquisition.id)
    if payer_note is not None:
        try:
            await emit_notify(acquisition.payer_id, payer_note, kind="gift_sent", no_toast=True)
        except Exception:
            log.exception("gift.payer_notification_failed", acquisition_id=acquisition.id)


async def pending_gift_toasts(session: AsyncSession, *, owner_id: int, after_id: int, limit: int) -> list[dict]:
    from ..api.utils import build_notify_payload

    event_key = literal(_GIFT_EVENT_KEY_PREFIX) + cast(UserGift.id, String) + literal(_GIFT_OWNER_EVENT_KEY_SUFFIX)
    rows = (await session.execute(
        select(UserGift, Notif).select_from(UserGift)
        .join(Gift, Gift.id == UserGift.gift_id)
        .join(Notif, and_(Notif.user_id == UserGift.owner_id, Notif.event_key == event_key))
        .where(UserGift.owner_id == owner_id, UserGift.payer_id != owner_id, UserGift.id > after_id,
               UserGift.toast_pending.is_(True), UserGift.active(), Gift.deleted_at.is_(None))
        .order_by(UserGift.id).limit(limit)
    )).all()
    await session.commit()
    profiles = await _sender_profiles([acquisition for acquisition, _note in rows])
    payloads = []
    for acquisition, note in rows:
        toast, extra = _gift_received_toast(acquisition, profiles)
        payloads.append(build_notify_payload(note, kind="gift_received", toast=toast, extra=extra))
    return payloads


async def dismiss_gift_toast(session: AsyncSession, acquisition_id: int, *, owner_id: int) -> None:
    await session.execute(
        update(UserGift).where(UserGift.id == acquisition_id, UserGift.owner_id == owner_id,
                               UserGift.payer_id != owner_id, UserGift.toast_pending.is_(True))
        .values(toast_pending=False)
    )
    await session.commit()


async def _publish_gift_changes(user_ids: set[int], balance_user_ids: set[int]) -> None:
    from ..realtime.sio import sio

    for uid in sorted(user_ids):
        try:
            await sio.emit("gifts_update", {"user_id": uid}, room=f"user:{uid}", namespace="/auth")
        except Exception:
            log.exception("gift.collection_sync_failed", user_id=uid)
    if not balance_user_ids:
        return

    try:
        async with SessionLocal() as session:
            balances = (await session.execute(
                select(User.id, User.dc_balance).where(User.id.in_(balance_user_ids))
            )).all()
    except Exception:
        log.exception("gift.balance_lookup_failed")
        return

    for uid, balance in balances:
        try:
            await sio.emit("dc_balance_update", {"user_id": uid, "dc_balance": balance},
                           room=f"user:{settings.PROTECTED_ADMIN_USER_ID}", namespace="/auth")
        except Exception:
            log.exception("gift.admin_balance_sync_failed", user_id=uid)


def _inventory_item(acquisition: UserGift, gift: Gift, quantity: int, profiles: dict[int, UserProfile], *,
                    reveal_anonymous_sender: bool = False) -> UserGiftOut:
    return UserGiftOut(
        id=acquisition.id, gift_id=gift.id, quantity=quantity, acquired_at=acquisition.acquired_at,
        preview_key=gift.preview_key, avif_key=gift.avif_key,
        sender=_gift_sender(acquisition, profiles, reveal_anonymous_sender=reveal_anonymous_sender),
    )


async def move_user_gift(session: AsyncSession, *, owner_id: int, payload: GiftMoveIn) -> None:
    acquisitions = list((await session.scalars(
        select(UserGift).join(Gift, Gift.id == UserGift.gift_id)
        .where(UserGift.owner_id == owner_id, UserGift.active(), Gift.deleted_at.is_(None))
        .order_by(UserGift.id).with_for_update(of=UserGift).execution_options(populate_existing=True)
    )).all())
    by_id = {acquisition.id: acquisition for acquisition in acquisitions}
    acquisition = by_id.get(payload.acquisition_id)
    target = by_id.get(payload.target_id)
    if acquisition is None or target is None:
        raise HTTPException(404, detail="gift_purchase_not_found")
    if acquisition is target:
        await session.commit()
        return

    acquisitions.sort(
        key=lambda row: (row.display_order is None, -(row.display_order or 0), row.acquired_at, row.id),
        reverse=True,
    )
    old_index = acquisitions.index(acquisition)
    acquisitions.pop(old_index)
    new_index = acquisitions.index(target) + (payload.place == "after")
    if new_index == old_index:
        await session.commit()
        return

    acquisitions.insert(new_index, acquisition)
    for index, row in enumerate(acquisitions):
        if row.display_order != index:
            row.display_order = index
    await session.commit()
    await _publish_gift_changes({owner_id}, set())


async def user_gifts(session: AsyncSession, user_id: int, *, grouped: bool, limit: int, offset: int,
                     reveal_anonymous_sender: bool = False) -> UserGiftsOut:
    filters = (UserGift.owner_id == user_id, UserGift.active(), Gift.deleted_at.is_(None))
    total = int(await session.scalar(
        select(func.count()).select_from(UserGift).join(Gift, Gift.id == UserGift.gift_id).where(*filters)
    ) or 0)
    order = (UserGift.display_order.asc().nulls_first(), UserGift.acquired_at.desc(), UserGift.id.desc())
    if grouped:
        ranked = select(
            UserGift.id.label("acquisition_id"),
            func.count().over(partition_by=UserGift.gift_id).label("quantity"),
            func.row_number().over(partition_by=UserGift.gift_id, order_by=order).label("rank"),
        ).select_from(UserGift).join(Gift, Gift.id == UserGift.gift_id).where(*filters).subquery()
        query = (
            select(UserGift, Gift, ranked.c.quantity)
            .select_from(UserGift)
            .join(ranked, ranked.c.acquisition_id == UserGift.id)
            .join(Gift, Gift.id == UserGift.gift_id).where(ranked.c.rank == 1)
        )
    else:
        query = select(UserGift, Gift, literal(1)).select_from(UserGift).join(Gift, Gift.id == UserGift.gift_id).where(*filters)
    rows = (await session.execute(query.order_by(*order).offset(offset).limit(limit + 1))).all()
    page = rows[:limit]
    profiles = await _sender_profiles(
        [acquisition for acquisition, _gift, _quantity in page], reveal_anonymous_sender=reveal_anonymous_sender,
    )
    items = [
        _inventory_item(acquisition, gift, int(quantity), profiles, reveal_anonymous_sender=reveal_anonymous_sender)
        for acquisition, gift, quantity in page
    ]
    return UserGiftsOut(items=items, total=total, has_more=len(rows) > limit)


async def user_gift_purchase(session: AsyncSession, acquisition_id: int, *, owner_id: int) -> UserGiftOut:
    row = (await session.execute(
        select(UserGift, Gift).select_from(UserGift).join(Gift, Gift.id == UserGift.gift_id).where(
            UserGift.id == acquisition_id, UserGift.owner_id == owner_id,
            UserGift.active(), Gift.deleted_at.is_(None),
        )
    )).first()
    if row is None:
        raise HTTPException(404, detail="gift_purchase_not_found")

    acquisition, gift = row
    return _inventory_item(acquisition, gift, 1, await _sender_profiles([acquisition]))


def _gift_removal_cost(acquisition: UserGift, now: datetime) -> int:
    if now - acquisition.acquired_at < timedelta(days=7):
        return acquisition.dc_cost // 2

    return 0


async def gift_removal_quote(session: AsyncSession, acquisition_id: int, *, owner_id: int) -> GiftRemovalQuoteOut:
    acquisition = await session.scalar(
        select(UserGift).join(Gift, Gift.id == UserGift.gift_id).where(
            UserGift.id == acquisition_id, UserGift.owner_id == owner_id,
            UserGift.active(), Gift.deleted_at.is_(None),
        )
    )
    if acquisition is None:
        raise HTTPException(404, detail="gift_purchase_not_found")

    return GiftRemovalQuoteOut(
        cost_dc=_gift_removal_cost(acquisition, datetime.now(timezone.utc)),
        dc_balance=await get_dc_balance(session, owner_id),
    )


async def remove_user_gift(session: AsyncSession, acquisition_id: int, *, owner_id: int,
                           max_cost_dc: int = 0) -> GiftRemovalOut:
    gift = await session.scalar(
        select(Gift).join(UserGift, UserGift.gift_id == Gift.id)
        .where(UserGift.id == acquisition_id, UserGift.owner_id == owner_id)
        .with_for_update(of=Gift, read=True).execution_options(populate_existing=True)
    )
    if gift is None:
        raise HTTPException(404, detail="gift_purchase_not_found")

    acquisition = await session.scalar(
        select(UserGift).where(UserGift.id == acquisition_id, UserGift.owner_id == owner_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if acquisition is None or acquisition.refunded_at is not None:
        raise HTTPException(404, detail="gift_purchase_not_found")

    if acquisition.removed_at is not None:
        balance = await get_dc_balance(session, owner_id)
        await session.commit()
        return GiftRemovalOut(dc_balance=balance)

    if gift.deleted_at is not None:
        raise HTTPException(404, detail="gift_purchase_not_found")

    now = datetime.now(timezone.utc)
    cost = _gift_removal_cost(acquisition, now)
    if cost > max_cost_dc:
        raise HTTPException(409, detail="gift_removal_cost_changed")

    if cost:
        try:
            operation = await adjust_dc_balance(session, owner_id, -cost, source="gift_removal", actor_id=owner_id)
        except HTTPException as exc:
            if exc.detail == "insufficient_dc_balance":
                raise HTTPException(409, detail="gift_removal_insufficient_balance") from None

            raise

        balance = operation.balance_after
        assert balance is not None
    else:
        balance = await get_dc_balance(session, owner_id)

    result = GiftRemovalOut(dc_balance=balance)
    acquisition.removed_at = now
    await session.commit()
    await _publish_gift_changes({owner_id}, {owner_id} if cost else set())
    return result


async def delete_gift_and_refund(session: AsyncSession, gift_id: int) -> Gift:
    from ..api.utils import emit_notify

    gift = await session.scalar(
        select(Gift).where(Gift.id == gift_id).with_for_update().execution_options(populate_existing=True)
    )
    if gift is None:
        raise HTTPException(404, detail="gift_not_found")

    if gift.deleted_at is not None:
        await session.commit()
        return gift

    acquisitions = (await session.scalars(
        select(UserGift).where(UserGift.gift_id == gift_id, UserGift.active())
        .order_by(UserGift.id).with_for_update()
    )).all()
    refunds: dict[int, int] = defaultdict(int)
    for acquisition in acquisitions:
        refunds[acquisition.owner_id] += acquisition.dc_cost
    notes: list[tuple[int, Notif]] = []
    for uid in sorted(refunds):
        owner = await lock_user_balance(session, uid)
        amount = refunds[uid]
        owner.dc_balance = checked_balance(owner.dc_balance, amount)
        note = await _persist_notice_once(
            session, user_id=uid, event_key=f"dc:gift_refund:{gift_id}:{uid}",
            title="Подарок удалён",
            text=f"Администратор удалил подарок №{gift_id}. Ваш баланс пополнен на {amount} DC.",
        )
        if note is not None:
            notes.append((uid, note))

    now = datetime.now(timezone.utc)
    gift.visible = False
    gift.deleted_at = now
    for acquisition in acquisitions:
        acquisition.refunded_at = now
        acquisition.refund_recipient_id = acquisition.owner_id
    await session.commit()

    for uid, note in notes:
        try:
            await emit_notify(uid, note, kind="gift_refund", no_toast=True)
        except Exception:
            log.exception("gift.refund_notification_failed", gift_id=gift_id, user_id=uid)

    owner_ids = set(refunds)
    await _publish_gift_changes(owner_ids, owner_ids)
    return gift
