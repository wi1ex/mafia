from __future__ import annotations
from datetime import datetime, timedelta, timezone
from contextlib import suppress
from math import ceil
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.game import Game
from ..models.notif import Notif
from ..models.subscription import SubscriptionGrant, UserSubscription
from ..models.user import User
from .game_scoring import RATING_MODE
from .nickname import SUBSCRIPTION_NICKNAME_CHANGE_LIMIT, set_user_nickname_changes
from .profile_theme import ensure_profile_theme_defaults


def rounded_game_minutes(started_at: datetime, finished_at: datetime) -> int:
    return max(0, ceil((finished_at - started_at).total_seconds() / 60))


async def reward_rating_host(session: AsyncSession, game: Game) -> Notif | None:
    if game.mode != RATING_MODE or not game.head_id:
        return None

    user = await session.scalar(select(User).where(User.id == game.head_id).with_for_update().execution_options(populate_existing=True))
    if user is None or user.deleted_at is not None:
        return None

    await session.refresh(game, attribute_names=["host_reward_minutes"])
    if game.host_reward_minutes is not None:
        return None

    game.host_reward_minutes = rounded_game_minutes(game.started_at, game.finished_at)
    user.rating_host_minutes += game.host_reward_minutes
    days = max(0, user.rating_host_minutes // 60 - user.rating_host_reward_days)
    await session.flush()
    if days == 0:
        return None

    try:
        async with session.begin_nested():
            now = datetime.now(timezone.utc)
            subscription = await session.scalar(
                select(UserSubscription).where(UserSubscription.user_id == user.id)
                .with_for_update().execution_options(populate_existing=True)
            )
            active = subscription is not None and subscription.starts_at <= now < subscription.ends_at
            if subscription is None:
                subscription = UserSubscription(user_id=user.id, starts_at=now, ends_at=now + timedelta(days=days))
                session.add(subscription)
            elif active:
                subscription.ends_at += timedelta(days=days)
            else:
                subscription.starts_at = now
                subscription.ends_at = now + timedelta(days=days)
            if not active:
                set_user_nickname_changes(user, SUBSCRIPTION_NICKNAME_CHANGE_LIMIT)
            await ensure_profile_theme_defaults(session, user.id, now=now)
            session.add(SubscriptionGrant(user_id=user.id, issued_at=now, reason="Ведущий РИ", days=days))
            note = Notif(
                user_id=user.id,
                title="Подписка",
                text=f"За проведение рейтинговых игр начислена подписка на {days} д.",
            )
            session.add(note)
            user.rating_host_reward_days += days
            await session.flush()
        return note

    except Exception:
        structlog.get_logger().exception("subscription.rating_host_grant_failed", game_id=game.id, days=days)
        return None


async def sync_rating_host_subscription(session: AsyncSession, user_id: int, note: Notif) -> None:
    from ..api.utils import emit_auth_profile_sync, emit_room_profile_theme_sync, notify_subscription_upsert
    from .user_cache import refresh_user_profile_cache
    from .profile_theme import resolve_profile_theme_state
    from .global_chat import emit_global_chat_profile_theme_sync

    user = await session.get(User, user_id)
    subscription = await session.scalar(select(UserSubscription).where(UserSubscription.user_id == user_id))
    if user is None or subscription is None:
        return

    with suppress(Exception):
        await notify_subscription_upsert(
            session, user, subscription, extended=True, note=note, notify_telegram=False,
        )

    with suppress(Exception):
        await refresh_user_profile_cache(session, user_id)
    theme = await resolve_profile_theme_state(session, user_id)
    with suppress(Exception):
        await emit_auth_profile_sync(user_id, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(user_id, theme.color, theme.icon)
    with suppress(Exception):
        await emit_global_chat_profile_theme_sync(user_id, theme.color, theme.icon)
