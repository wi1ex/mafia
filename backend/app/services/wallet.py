from __future__ import annotations
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal
import structlog
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.settings import settings
from ..models.coin_purchase import CoinPurchase
from ..models.notif import Notif
from ..models.settings import AppSettings
from ..models.subscription import UserSubscription
from ..models.subscription_purchase import SubscriptionPurchase
from ..models.user import User
from .nickname import SUBSCRIPTION_NICKNAME_CHANGE_LIMIT, set_user_nickname_changes
from .notification_texts import format_subscription_purchase_duration, format_subscription_until
from .profile_theme import compute_subscription_end, ensure_profile_theme_defaults

log = structlog.get_logger()
MAX_DC = 2**63 - 1
SUBSCRIPTION_PLANS = {
    "week": (7, 0, 7),
    "month": (0, 1, 27),
    "quarter": (0, 3, 75),
    "year": (0, 12, 275),
}


async def get_dc_balance(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(User.dc_balance).where(User.id == int(user_id))) or 0)


async def lock_user_balance(session: AsyncSession, user_id: int) -> User:
    uid = int(user_id)
    user = await session.scalar(select(User).where(User.id == uid).with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise HTTPException(404, detail="user_not_found")

    return user


async def lock_dc_request(session: AsyncSession, request_id: str, *, journal: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"dc:request:{journal}:{request_id}"},
    )


async def ensure_purchase_access(session: AsyncSession, user: User) -> None:
    from ..api.utils import fetch_active_sanction
    from ..security.parameters import get_cached_settings
    if user.deleted_at is not None:
        raise HTTPException(403, detail="user_deleted")

    if await fetch_active_sanction(session, int(user.id), "ban"):
        raise HTTPException(403, detail="user_banned")

    if get_cached_settings().verification_restrictions and not user.telegram_id:
        raise HTTPException(403, detail="telegram_verification_required")

    if user.rules_acceptance_required:
        raise HTTPException(403, detail="rules_required")


async def ensure_payments_enabled(session: AsyncSession) -> None:
    enabled = await session.scalar(
        select(AppSettings.payments_enabled).where(AppSettings.id == 1).with_for_update(read=True)
    )
    if enabled is False:
        raise HTTPException(503, detail="payments_disabled")


async def ensure_gift_recipient_access(session: AsyncSession, recipient: User) -> None:
    from ..api.utils import fetch_active_sanction

    if recipient.deleted_at is not None:
        raise HTTPException(403, detail="gift_recipient_deleted")

    if await fetch_active_sanction(session, int(recipient.id), "ban"):
        raise HTTPException(403, detail="gift_recipient_banned")

    verification_restrictions = await session.scalar(
        select(AppSettings.verification_restrictions).where(AppSettings.id == 1)
    )
    if verification_restrictions is None:
        verification_restrictions = settings.VERIFICATION_RESTRICTIONS
    if verification_restrictions and not recipient.telegram_id:
        raise HTTPException(403, detail="gift_recipient_unverified")


def checked_balance(before: int, delta: int) -> int:
    after = int(before) + int(delta)
    if after < 0:
        raise HTTPException(409, detail="insufficient_dc_balance")

    if after > MAX_DC:
        raise HTTPException(422, detail="dc_balance_too_large")

    return after


async def adjust_dc_balance(session: AsyncSession, user_id: int, delta: int, *, source: str, actor_id: int | None = None, request_id: str | None = None) -> CoinPurchase:
    if isinstance(delta, bool) or not isinstance(delta, int) or not delta:
        raise HTTPException(422, detail="dc_quantity_invalid")

    user = await lock_user_balance(session, user_id)
    if user.deleted_at is not None:
        raise HTTPException(403, detail="user_deleted")

    if request_id:
        await lock_dc_request(session, str(request_id), journal="coin")
        existing = await session.scalar(select(CoinPurchase).where(CoinPurchase.request_id == str(request_id)))
        if existing:
            if existing.user_id != int(user_id) or existing.source != source or existing.quantity != abs(delta) or existing.actor_id != actor_id:
                raise HTTPException(409, detail="idempotency_conflict")

            return existing

    before = int(user.dc_balance)
    user.dc_balance = checked_balance(before, delta)
    operation = CoinPurchase(user_id=int(user_id), source=source, quantity=abs(delta), actor_id=actor_id,
                             request_id=str(request_id) if request_id else None, status="processed",
                             balance_before=before, balance_after=user.dc_balance, processed_at=datetime.now(timezone.utc))
    session.add(operation)
    await session.flush()
    operation.result = {"operation_id": operation.id, "dc_balance": user.dc_balance}
    return operation


async def record_admin_subscription(session: AsyncSession, *, user_id: int, months: int = 0, days: int = 0,
                                    ends_before: datetime | None, ends_after: datetime, starts_at: datetime | None = None,
                                    actor_id: int | None = None, source: str = "admin") -> SubscriptionPurchase:
    purchase = SubscriptionPurchase(user_id=int(user_id), source=source, months=months, days=days, dc_cost=0,
                                    status="processed", actor_id=actor_id, starts_at=starts_at,
                                    ends_before=ends_before, ends_after=ends_after, processed_at=datetime.now(timezone.utc))
    session.add(purchase)
    await session.flush()
    return purchase


def subscription_gift_is_anonymous(result: object) -> bool:
    return isinstance(result, dict) and result.get("anonymous") is True


async def buy_subscription(session: AsyncSession, *, user_id: int, plan: str, request_id: str,
                           recipient_id: int | None = None, anonymous: bool = False) -> dict:
    if not isinstance(plan, str) or plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(422, detail="subscription_plan_invalid")

    if recipient_id is not None:
        if type(recipient_id) is not int or not 0 < recipient_id <= MAX_DC:
            raise HTTPException(422, detail="gift_recipient_invalid")

        if recipient_id == user_id:
            raise HTTPException(422, detail="gift_self_not_allowed")

    if anonymous and recipient_id is None:
        raise HTTPException(422, detail="gift_anonymous_requires_recipient")

    target_id = recipient_id if recipient_id is not None else user_id
    source = "gift" if recipient_id is not None else "dc"
    actor_id = user_id if source == "gift" else None
    days, months, cost = SUBSCRIPTION_PLANS[plan]
    locked_users = {}
    for uid in sorted({user_id, target_id}):
        try:
            locked_users[uid] = await lock_user_balance(session, uid)
        except HTTPException as exc:
            if source == "gift" and uid == target_id and exc.status_code == 404:
                raise HTTPException(404, detail="gift_recipient_not_found") from None

            raise

    user = locked_users[user_id]
    recipient = locked_users[target_id]
    await lock_dc_request(session, str(request_id), journal="subscription")
    existing = await session.scalar(select(SubscriptionPurchase).where(SubscriptionPurchase.request_id == str(request_id)))
    if existing:
        existing_result = existing.result or {}
        if (existing.user_id != target_id or existing.days != days or existing.months != months
                or existing.source != source or existing.actor_id != actor_id
                or subscription_gift_is_anonymous(existing_result) != anonymous):
            raise HTTPException(409, detail="idempotency_conflict")

        result = {key: value for key, value in existing_result.items()
                  if key in {"purchase_id", "dc_balance", "subscription_until", "subscription_active",
                             "recipient_id", "recipient_username"}}
        result["anonymous"] = anonymous
        await session.commit()
        await notify_subscription_purchase(session, existing)
        return result

    await ensure_payments_enabled(session)
    await ensure_purchase_access(session, user)
    if source == "gift":
        await ensure_gift_recipient_access(session, recipient)

    now = datetime.now(timezone.utc)
    subscription = await session.scalar(select(UserSubscription).where(UserSubscription.user_id == target_id).with_for_update().execution_options(populate_existing=True))
    active = bool(subscription and subscription.starts_at <= now < subscription.ends_at)
    ends_before = subscription.ends_at if subscription else None
    base = subscription.ends_at if active else now
    try:
        ends_after = compute_subscription_end(base, days=days, months=months, active=active)
    except (OverflowError, ValueError):
        raise HTTPException(422, detail="subscription_duration_too_large") from None

    before = int(user.dc_balance)
    user.dc_balance = checked_balance(before, -cost)
    if subscription is None:
        subscription = UserSubscription(user_id=target_id, starts_at=now, ends_at=ends_after)
        session.add(subscription)
    else:
        subscription.ends_at = ends_after
        if not active:
            subscription.starts_at = now
    if not active:
        set_user_nickname_changes(recipient, SUBSCRIPTION_NICKNAME_CHANGE_LIMIT)
    await session.flush()
    await ensure_profile_theme_defaults(session, target_id, now=now)
    purchase = SubscriptionPurchase(user_id=target_id, source=source, actor_id=actor_id,
                                    days=days, months=months, dc_cost=cost,
                                    request_id=str(request_id), status="processed", starts_at=subscription.starts_at,
                                    ends_before=ends_before, ends_after=ends_after, balance_before=before,
                                    balance_after=user.dc_balance, processed_at=now)
    session.add(purchase)
    await session.flush()
    result = {"purchase_id": purchase.id, "dc_balance": user.dc_balance,
              "subscription_until": ends_after.isoformat(), "subscription_active": True,
              "recipient_id": target_id, "recipient_username": recipient.username, "anonymous": anonymous}
    purchase.result = {**result, "extended": active, "sender_id": user_id,
                       "sender_username": user.username}
    note = await _persist_subscription_purchase_notice(session, purchase)
    sender_note = await _persist_subscription_gift_sender_notice(session, purchase) if source == "gift" else None
    await session.commit()
    await notify_subscription_purchase(session, purchase, note=note, sender_note=sender_note)
    return result


def money_text(amount: Decimal | None, currency: str | None) -> str:
    return f"{(amount or Decimal(0)):.2f}".replace(".", ",") + " " + {"RUB": "₽", "USD": "$", "EUR": "€"}.get(currency or "", currency or "")


async def _persist_notice_once(session: AsyncSession, *, user_id: int, event_key: str, title: str, text: str) -> Notif | None:
    statement = (
        pg_insert(Notif)
        .values(user_id=user_id, event_key=event_key, title=title, text=text)
        .on_conflict_do_nothing()
        .returning(Notif)
    )
    return (await session.scalars(statement)).one_or_none()


async def persist_coin_operation_notice(session: AsyncSession, operation: CoinPurchase) -> Notif | None:
    if operation.status != "processed" or operation.user_id is None:
        return None

    if operation.source == "lava":
        title = "Баланс пополнен"
        text = (
            f"На ваш баланс зачислено {operation.quantity} DC. "
            f"Оплачено: {money_text(operation.amount, operation.currency)}. "
            f"Баланс: {operation.balance_after} DC."
        )
    elif operation.source == "admin_grant":
        title = "Начисление монет"
        text = f"Администратор бесплатно начислил вам {operation.quantity} DC. Баланс: {operation.balance_after} DC."
    else:
        return None

    return await _persist_notice_once(
        session, user_id=operation.user_id, event_key=f"dc:coin:{operation.id}", title=title, text=text,
    )


async def _persist_subscription_purchase_notice(session: AsyncSession, purchase: SubscriptionPurchase) -> Notif | None:
    action = "продлили" if (purchase.result or {}).get("extended") else "купили"
    duration = format_subscription_purchase_duration(days=purchase.days, months=purchase.months)
    end = format_subscription_until(purchase.ends_after)
    title = "Подписка"
    if purchase.source == "gift":
        title = "Вам подарили подписку"
        if subscription_gift_is_anonymous(purchase.result):
            text = f"Вы получили анонимный подарок — подписку на {duration}. Подписка действует до {end}."
        else:
            sender = (purchase.result or {}).get("sender_username") or f"user{purchase.actor_id}"
            text = f"{sender} подарил вам подписку на {duration}. Подписка действует до {end}."
    else:
        text = (
            f"Вы {action} подписку на {duration} за {purchase.dc_cost} DC. "
            f"Подписка действует до {end}. Баланс: {purchase.balance_after} DC."
        )
    return await _persist_notice_once(
        session, user_id=purchase.user_id, event_key=f"dc:subscription:{purchase.id}", title=title, text=text,
    )


async def _persist_subscription_gift_sender_notice(session: AsyncSession, purchase: SubscriptionPurchase) -> Notif | None:
    recipient = (purchase.result or {}).get("recipient_username") or f"user{purchase.user_id}"
    duration = format_subscription_purchase_duration(days=purchase.days, months=purchase.months)
    action = "Вы анонимно подарили" if subscription_gift_is_anonymous(purchase.result) else "Вы подарили"
    text = (
        f"{action} {recipient} подписку на {duration}. "
        f"Списано: {purchase.dc_cost} DC. Баланс: {purchase.balance_after} DC."
    )
    return await _persist_notice_once(
        session, user_id=purchase.actor_id, event_key=f"dc:subscription:{purchase.id}:sender",
        title="Подарок подписки", text=text,
    )


async def sync_wallet_profile(session: AsyncSession, user_id: int, *, balance_only: bool = False) -> None:
    from ..api.utils import emit_auth_profile_sync, emit_room_profile_theme_sync
    from .user_cache import refresh_user_profile_cache
    from .profile_theme import resolve_profile_theme_state
    from .global_chat import emit_global_chat_profile_theme_sync

    if not balance_only:
        await refresh_user_profile_cache(session, user_id)
    await emit_auth_profile_sync(user_id)

    from ..realtime.sio import sio
    await sio.emit("dc_balance_update", {"user_id": user_id, "dc_balance": await get_dc_balance(session, user_id)},
                   room=f"user:{settings.PROTECTED_ADMIN_USER_ID}", namespace="/auth")
    if balance_only:
        return

    theme = await resolve_profile_theme_state(session, user_id)
    await emit_room_profile_theme_sync(user_id, theme.color, theme.icon)
    await emit_global_chat_profile_theme_sync(user_id, theme.color, theme.icon)


async def notify_coin_operation(session: AsyncSession, operation: CoinPurchase, *, note: Notif | None = None) -> None:
    if operation.status != "processed" or operation.user_id is None:
        return

    uid = int(operation.user_id)
    operation_id = operation.id
    try:
        if note is not None:
            from ..api.utils import emit_notify, schedule_contact_request_admin_telegram_message

            toast_kind = "coin_topup" if operation.source == "lava" else "coin_grant"
            await emit_notify(uid, note, kind="coins", toast={"kind": toast_kind, "title": "Баланс"})
            if operation.source == "lava":
                user = await session.get(User, uid)
                schedule_contact_request_admin_telegram_message(
                    "Покупка монет\n\n"
                    f"Пользователь: {user.username if user else f'user{uid}'}\n"
                    f"ID пользователя: {uid}\nНачислено: {operation.quantity} DC\n"
                    f"Оплачено: {money_text(operation.amount, operation.currency)}\n"
                    f"Баланс после операции: {operation.balance_after} DC\n"
                    f"Заказ: №{operation_id}\nСчёт Lava: {operation.invoice_id}"
                )
    except Exception:
        log.exception("dc.coin_notification_failed", operation_id=operation_id)
        with suppress(Exception):
            await session.rollback()
    with suppress(Exception):
        await sync_wallet_profile(session, uid)


async def notify_subscription_gift(session: AsyncSession, purchase: SubscriptionPurchase, *,
                                   note: Notif | None = None, sender_note: Notif | None = None) -> None:
    from ..api.utils import emit_notify

    recipient_id = int(purchase.user_id)
    sender_id = int(purchase.actor_id)
    purchase_id = purchase.id
    metadata = purchase.result or {}
    anonymous = subscription_gift_is_anonymous(metadata)
    gift = {
        "recipient_id": recipient_id,
        "duration": format_subscription_purchase_duration(days=purchase.days, months=purchase.months),
        "subscription_until": purchase.ends_after.isoformat(),
        "purchase_id": purchase_id,
    }
    if anonymous:
        gift["anonymous"] = True
    else:
        gift["sender_id"] = sender_id
        gift["sender_username"] = metadata.get("sender_username") or f"user{sender_id}"

    recipient_extra = {"subscription_gift": gift}
    recipient_toast = {"title": "Подписка"}
    if note is not None and not anonymous:
        sender_profile = {}
        try:
            from ..core.db import SessionLocal
            from .user_cache import get_user_profile_cached

            async with SessionLocal() as profile_session:
                sender_profile = await get_user_profile_cached(profile_session, sender_id) or {}
        except Exception:
            log.exception("dc.subscription_gift_sender_profile_failed", purchase_id=purchase_id)
        recipient_extra["user"] = {
            "id": sender_id,
            "username": gift["sender_username"],
            "avatar_name": sender_profile.get("avatar_name"),
            "role": sender_profile.get("role"),
            "theme_color": sender_profile.get("theme_color"),
            "theme_icon": sender_profile.get("theme_icon"),
        }
        recipient_toast["text"] = (
            f"Срок: {gift['duration']}. Подписка действует до {format_subscription_until(purchase.ends_after)}."
        )
    for uid, message, kind, no_toast, toast, extra in (
        (recipient_id, note, "subscription_gift", False, recipient_toast, recipient_extra),
        (sender_id, sender_note, "subscription", True, None, None),
    ):
        if message is not None:
            try:
                await emit_notify(uid, message, kind=kind, toast=toast, no_toast=no_toast, extra=extra)
            except Exception:
                log.exception("dc.subscription_gift_notification_failed", purchase_id=purchase_id, user_id=uid)
    for uid in sorted({sender_id, recipient_id}):
        try:
            await sync_wallet_profile(session, uid, balance_only=anonymous and uid == sender_id)
        except Exception:
            log.exception("dc.subscription_gift_profile_sync_failed", purchase_id=purchase_id, user_id=uid)
            with suppress(Exception):
                await session.rollback()


async def notify_subscription_purchase(session: AsyncSession, purchase: SubscriptionPurchase, *,
                                       note: Notif | None = None, sender_note: Notif | None = None) -> None:
    if purchase.source == "gift" and purchase.status == "processed" and purchase.user_id and purchase.actor_id:
        await notify_subscription_gift(session, purchase, note=note, sender_note=sender_note)
        return

    if purchase.source != "dc" or purchase.status != "processed" or not purchase.user_id:
        return

    uid = int(purchase.user_id)
    purchase_id = purchase.id
    try:
        if note is not None:
            from ..api.utils import emit_notify

            await emit_notify(uid, note, kind="subscription", toast={"kind": "subscription_purchase"})
    except Exception:
        log.exception("dc.subscription_notification_failed", purchase_id=purchase_id)
        with suppress(Exception):
            await session.rollback()
    with suppress(Exception):
        await sync_wallet_profile(session, uid)
