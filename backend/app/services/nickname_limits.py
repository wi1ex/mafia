from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import case, exists, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.db import SessionLocal
from ..models.subscription import UserSubscription
from ..models.user import User

MIN_NICKNAME_CHANGE_LIMIT = 0
MAX_NICKNAME_CHANGE_LIMIT = 30
FREE_NICKNAME_CHANGE_LIMIT = 1
SUBSCRIPTION_NICKNAME_CHANGE_LIMIT = 30
SUBSCRIPTION_EXPIRED_NICKNAME_CHANGE_RESET = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_nickname_changes_left(value: object) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        return 0

    return min(MAX_NICKNAME_CHANGE_LIMIT, max(MIN_NICKNAME_CHANGE_LIMIT, parsed))


def set_user_nickname_changes(user: User, value: int) -> int:
    next_value = normalize_nickname_changes_left(value)
    user.nickname_changes_left = next_value
    return next_value


async def _set_monthly_nickname_change_limits(session: AsyncSession, *, now: datetime) -> int:
    active_subscription = exists().where(
        UserSubscription.user_id == User.id,
        UserSubscription.starts_at <= now,
        UserSubscription.ends_at > now,
    )
    limit_value = case(
        (active_subscription, SUBSCRIPTION_NICKNAME_CHANGE_LIMIT),
        else_=FREE_NICKNAME_CHANGE_LIMIT,
    )
    result = await session.execute(
        update(User)
        .where(User.deleted_at.is_(None))
        .values(nickname_changes_left=limit_value)
    )
    return int(result.rowcount or 0)


async def reset_monthly_nickname_change_limits(*, now: datetime | None = None) -> int:
    current = now or _utc_now()
    local_current = current.astimezone() if current.tzinfo is not None else current.replace(tzinfo=timezone.utc).astimezone()
    if local_current.day != 1:
        return 0

    async with SessionLocal() as session:
        affected = await _set_monthly_nickname_change_limits(session, now=current)
        await session.commit()
        return affected


async def reset_nickname_changes_after_subscription_expired(
    session: AsyncSession,
    *,
    user_id: int,
) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == int(user_id), User.nickname_changes_left > FREE_NICKNAME_CHANGE_LIMIT)
        .values(nickname_changes_left=SUBSCRIPTION_EXPIRED_NICKNAME_CHANGE_RESET)
    )
    return int(result.rowcount or 0) > 0
