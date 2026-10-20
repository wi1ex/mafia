from __future__ import annotations
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
import structlog
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.log import AppLog
from ..models.notif import Notif
from ..models.settings import AppSettings
from ..models.subscription import (
    SubscriptionGrant,
    UserSubscription,
)
from ..models.user import User
from ..schemas.subscription_roulette import (
    SubscriptionRouletteNotificationOut,
    SubscriptionRouletteSpinOut,
    SubscriptionRouletteStatusOut,
)
from .nickname import (
    SUBSCRIPTION_NICKNAME_CHANGE_LIMIT,
    normalize_nickname_changes_left,
    set_user_nickname_changes,
)
from .profile_theme import compute_subscription_end, ensure_profile_theme_defaults

log = structlog.get_logger()
WIN_ACTION = "subscription_roulette_win"


async def start_roulette_round(session: AsyncSession, settings: AppSettings) -> int:
    settings.subscription_roulette_state = settings.subscription_roulette_round + 1
    result = await session.execute(
        update(User).values(
            subscription_roulette_days=None,
        ).execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)


@dataclass(slots=True)
class RouletteResult:
    response: SubscriptionRouletteSpinOut
    user_id: int
    role: str
    created: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _valid_days(value: int | None) -> bool:
    return value is not None and 1 <= value <= 30


def _notification_payload(note: Notif | None) -> SubscriptionRouletteNotificationOut | None:
    if note is None:
        return None

    return SubscriptionRouletteNotificationOut(
        id=note.id,
        title=note.title,
        text=note.text,
        date=note.created_at,
        read=note.read_at is not None,
    )


async def _previous_note(session: AsyncSession, grant: SubscriptionGrant | None) -> Notif | None:
    if grant is None or grant.source_log_id is None:
        return None

    entry = await session.get(AppLog, grant.source_log_id)
    if entry is None or entry.action != WIN_ACTION or entry.user_id != grant.user_id:
        return None

    try:
        details = json.loads(entry.details)
        notification_id = int(details.get("notification_id") or 0)
    except (ValueError, TypeError, AttributeError):
        return None

    if notification_id <= 0:
        return None

    return await session.scalar(select(Notif).where(Notif.id == notification_id, Notif.user_id == grant.user_id))


def _status(
    *,
    round_id: int,
    enabled: bool,
    user: User,
    days: int | None,
    subscription: UserSubscription | None,
    note: Notif | None = None,
) -> SubscriptionRouletteStatusOut:
    verified = bool(user.telegram_id)
    return SubscriptionRouletteStatusOut(
        round_id=round_id,
        enabled=enabled,
        verified=verified,
        eligible=enabled and verified and days is None,
        already_spun=days is not None,
        subscription_roulette_days=days,
        subscription_until=subscription.ends_at if subscription is not None else None,
        notification=_notification_payload(note),
    )


async def _load_grant(session: AsyncSession, user_id: int, round_id: int) -> SubscriptionGrant | None:
    rows = await session.execute(
        select(SubscriptionGrant, AppLog.details).outerjoin(
            AppLog, (AppLog.id == SubscriptionGrant.source_log_id)
            & (AppLog.user_id == user_id) & (AppLog.action == WIN_ACTION),
        ).where(
            SubscriptionGrant.user_id == user_id,
            SubscriptionGrant.reason == "Лотерея",
        ).order_by(SubscriptionGrant.id.desc()).execution_options(populate_existing=True)
    )
    for grant, details in rows:
        try:
            stored_round = json.loads(details).get("round_id", 0) if details else 0
        except (ValueError, TypeError, AttributeError):
            stored_round = 0
        if type(stored_round) is int and stored_round == round_id:
            return grant

    return None


async def get_roulette_status(session: AsyncSession, user_id: int, *, round_id: int | None = None,) -> SubscriptionRouletteStatusOut:
    settings = await session.scalar(
        select(AppSettings).where(AppSettings.id == 1)
        .with_for_update(read=True).execution_options(populate_existing=True)
    )
    user = await session.scalar(
        select(User).where(User.id == user_id).execution_options(populate_existing=True)
    )
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    current_round = settings.subscription_roulette_round if settings is not None else 0
    target_round = current_round if round_id is None else round_id
    enabled = bool(settings is not None and settings.subscription_roulette_enabled)
    grant = await _load_grant(session, user_id, target_round) if target_round <= current_round else None
    if target_round != current_round and grant is None:
        raise HTTPException(status_code=409, detail="subscription_roulette_round_changed")

    if grant is not None and not _valid_days(grant.days):
        raise HTTPException(status_code=503, detail="subscription_roulette_result_unavailable")

    days = user.subscription_roulette_days if target_round == current_round else None
    if days is None and grant is not None and _valid_days(grant.days):
        days = grant.days
    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    )
    return _status(
        round_id=target_round, enabled=enabled, user=user, days=days, subscription=subscription,
        note=await _previous_note(session, grant),
    )


def _notification_text(days: int, subscription: UserSubscription, *, extended: bool) -> str:
    from ..api.utils import format_subscription_purchase_duration, format_subscription_until

    duration = format_subscription_purchase_duration(days=days)
    action = "продлена" if extended else "активирована"
    return (
        f"Вы выиграли {duration} подписки в лотерее. "
        f"Подписка {action} до {format_subscription_until(subscription.ends_at)}."
    )


def _add_win_log(session: AsyncSession, user: User, details: dict) -> AppLog:
    entry = AppLog(
        user_id=user.id, username=user.username, action=WIN_ACTION,
        details=json.dumps(details, ensure_ascii=False, separators=(",", ":")),
    )
    session.add(entry)
    return entry


async def _spin_once(session: AsyncSession, user_id: int, *, round_id: int | None) -> RouletteResult:
    settings = await session.scalar(
        select(AppSettings).where(AppSettings.id == 1)
        .with_for_update(read=True).execution_options(populate_existing=True)
    )
    enabled = bool(settings is not None and settings.subscription_roulette_enabled)
    user = await session.scalar(
        select(User).where(User.id == user_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if settings is None:
        raise HTTPException(status_code=503, detail="subscription_roulette_settings_unavailable")

    current_round = settings.subscription_roulette_round
    round_id = current_round if round_id is None else round_id

    grant = await _load_grant(session, user_id, round_id) if round_id <= current_round else None
    if round_id != current_round:
        if grant is None:
            raise HTTPException(status_code=409, detail="subscription_roulette_round_changed")

        if not _valid_days(grant.days):
            raise HTTPException(status_code=503, detail="subscription_roulette_result_unavailable")

        subscription = await session.scalar(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        )
        response = SubscriptionRouletteSpinOut(**_status(
            round_id=round_id, enabled=enabled, user=user, days=grant.days,
            subscription=subscription, note=await _previous_note(session, grant),
        ).model_dump())
        await session.commit()
        return RouletteResult(response=response, user_id=user_id, role=user.role)

    days = user.subscription_roulette_days
    if days is None and grant is not None:
        if not _valid_days(grant.days):
            raise HTTPException(status_code=503, detail="subscription_roulette_result_unavailable")

        days = user.subscription_roulette_days = grant.days

    if days is not None:
        subscription = await session.scalar(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        )
        note = await _previous_note(session, grant)
        response = SubscriptionRouletteSpinOut(**_status(
            round_id=round_id, enabled=enabled, user=user, days=days, subscription=subscription, note=note,
        ).model_dump())
        await session.commit()
        return RouletteResult(response=response, user_id=user_id, role=user.role)

    if not enabled:
        raise HTTPException(status_code=403, detail="subscription_roulette_disabled")

    if not user.telegram_id:
        raise HTTPException(status_code=403, detail="subscription_roulette_verification_required")

    days = secrets.randbelow(30) + 1
    now = _utc_now()
    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    previous_until = subscription.ends_at if subscription is not None else None
    extended = bool(subscription and subscription.starts_at <= now < subscription.ends_at)
    if subscription is None:
        subscription = UserSubscription(
            user_id=user_id, starts_at=now,
            ends_at=compute_subscription_end(now, months=0, days=days),
        )
        session.add(subscription)
    elif extended:
        subscription.ends_at = compute_subscription_end(subscription.ends_at, months=0, days=days)
    else:
        subscription.starts_at = now
        subscription.ends_at = compute_subscription_end(now, months=0, days=days)
    if extended:
        user.nickname_changes_left = normalize_nickname_changes_left(user.nickname_changes_left)
    else:
        set_user_nickname_changes(user, SUBSCRIPTION_NICKNAME_CHANGE_LIMIT)

    user.subscription_roulette_days = days
    grant = SubscriptionGrant(
        user_id=user_id, issued_at=now, reason="Лотерея",
        months=0, days=days,
    )
    note = Notif(
        user_id=user_id, title="Подписка", created_at=now,
        text=_notification_text(days, subscription, extended=extended),
    )
    session.add_all([grant, note])
    await session.flush()
    await ensure_profile_theme_defaults(session, user_id, now=now)
    entry = _add_win_log(session, user, {
        "round_id": round_id,
        "days": days,
        "subscription_grant_id": grant.id,
        "notification_id": note.id,
        "previous_until": previous_until.isoformat() if previous_until is not None else None,
        "starts_at": subscription.starts_at.isoformat(),
        "ends_at": subscription.ends_at.isoformat(),
    })
    await session.flush()
    grant.source_log_id = entry.id
    response = SubscriptionRouletteSpinOut(**_status(
        round_id=round_id, enabled=enabled, user=user, days=days, subscription=subscription, note=note,
    ).model_dump())
    await session.commit()
    return RouletteResult(response=response, user_id=user_id, role=user.role, created=True)


async def spin_roulette(
    session: AsyncSession, user_id: int, *, round_id: int | None = None,
) -> RouletteResult:
    try:
        return await _spin_once(session, user_id, round_id=round_id)

    except BaseException:
        await session.rollback()
        raise


async def publish_roulette_win(session: AsyncSession, result: RouletteResult) -> None:
    if not result.created:
        return

    try:
        await _publish_roulette_win(session, result)
    except Exception:
        log.warning("subscription_roulette.delivery_failed", uid=result.user_id, effect="delivery", exc_info=True)


async def deliver_roulette_win(result: RouletteResult) -> None:
    from ..core.db import SessionLocal

    try:
        async with SessionLocal() as session:
            await publish_roulette_win(session, result)
    except Exception:
        log.warning("subscription_roulette.delivery_failed", uid=result.user_id, effect="session", exc_info=True)


async def _publish_roulette_win(session: AsyncSession, result: RouletteResult) -> None:
    from ..api.utils import (
        emit_auth_profile_sync, emit_notify, emit_room_profile_theme_sync,
    )
    from .global_chat import emit_global_chat_profile_theme_sync
    from .profile_theme import resolve_profile_theme_state
    from .user_cache import refresh_user_profile_cache

    uid = result.user_id
    effects = [
        ("cache", lambda: refresh_user_profile_cache(session, uid)),
        ("profile", lambda: emit_auth_profile_sync(uid, role=result.role)),
    ]
    for label, effect in effects:
        try:
            await effect()
        except Exception:
            await session.rollback()
            log.warning("subscription_roulette.delivery_failed", uid=uid, effect=label, exc_info=True)
    try:
        state = await resolve_profile_theme_state(session, uid)
        await emit_room_profile_theme_sync(uid, state.color, state.icon)
        await emit_global_chat_profile_theme_sync(uid, state.color, state.icon)
    except Exception:
        await session.rollback()
        log.warning("subscription_roulette.delivery_failed", uid=uid, effect="theme", exc_info=True)
    if result.response.notification is not None:
        payload = result.response.notification
        note = Notif(
            id=payload.id, user_id=uid, title=payload.title, text=payload.text,
            created_at=payload.date, read_at=payload.date if payload.read else None,
        )
        try:
            await emit_notify(uid, note, kind="subscription", extra={
                "source": "subscription_roulette", "round_id": result.response.round_id,
            })
        except Exception:
            log.warning("subscription_roulette.delivery_failed", uid=uid, effect="notification", exc_info=True)
