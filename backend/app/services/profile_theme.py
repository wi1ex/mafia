from __future__ import annotations
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.subscription import UserSubscription
from ..models.user import User

PROFILE_THEME_COLORS: tuple[str, ...] = (
    "violet",
    "mulberry",
    "garnet",
    "terracotta",
    "amber",
    "olive",
    "emerald",
    "lagoon",
    "azure",
    "midnight",
)
PROFILE_THEME_DEFAULT = "terracotta"


@dataclass(slots=True)
class ProfileThemeState:
    subscription_active: bool = False
    subscription_started_at: datetime | None = None
    subscription_until: datetime | None = None
    color: str | None = None


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


def normalize_profile_theme_color(raw: object) -> str:
    value = str(raw or "").strip().lower()
    if value not in PROFILE_THEME_COLORS:
        raise ValueError("profile_theme_invalid")

    return value


def add_months(dt: datetime, months: int) -> datetime:
    months_i = max(0, int(months or 0))
    if months_i <= 0:
        return dt

    month_index = (dt.month - 1) + months_i
    year = dt.year + (month_index // 12)
    month = (month_index % 12) + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)


def compute_subscription_end(starts_at: datetime, *, months: int = 0, days: int = 0) -> datetime:
    result = starts_at
    if int(months or 0) > 0:
        result = add_months(result, int(months or 0))
    if int(days or 0) > 0:
        result = result + timedelta(days=int(days or 0))
    return result


async def fetch_active_subscriptions(session: AsyncSession, user_ids: Iterable[int | str], *, now: datetime | None = None) -> dict[int, UserSubscription]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    current = now or datetime.now(timezone.utc)
    rows = await session.execute(
        select(UserSubscription).where(
            UserSubscription.user_id.in_(ids),
            UserSubscription.starts_at <= current,
            UserSubscription.ends_at > current,
        )
    )
    return {
        int(row.user_id): row
        for row in rows.scalars().all()
        if row.user_id is not None
    }


async def fetch_profile_theme_preferences(session: AsyncSession, user_ids: Iterable[int | str]) -> dict[int, str]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    rows = await session.execute(
        select(User.id, User.profile_theme_color).where(User.id.in_(ids))
    )
    out: dict[int, str] = {}
    for user_id_raw, color_raw in rows.all():
        try:
            uid = int(user_id_raw)
        except Exception:
            continue
        try:
            out[uid] = normalize_profile_theme_color(color_raw)
        except ValueError:
            continue
    return out


async def resolve_profile_theme_states(session: AsyncSession, user_ids: Iterable[int | str], *, now: datetime | None = None) -> dict[int, ProfileThemeState]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    active_subscriptions = await fetch_active_subscriptions(session, ids, now=now)
    preferences = await fetch_profile_theme_preferences(session, ids)
    out: dict[int, ProfileThemeState] = {}
    for uid in ids:
        subscription = active_subscriptions.get(uid)
        if not subscription:
            out[uid] = ProfileThemeState()
            continue
        out[uid] = ProfileThemeState(
            subscription_active=True,
            subscription_started_at=subscription.starts_at,
            subscription_until=subscription.ends_at,
            color=preferences.get(uid) or PROFILE_THEME_DEFAULT,
        )
    return out


async def resolve_profile_theme_state(session: AsyncSession, user_id: int | str, *, now: datetime | None = None) -> ProfileThemeState:
    uid = int(user_id)
    states = await resolve_profile_theme_states(session, [uid], now=now)
    return states.get(uid) or ProfileThemeState()


async def upsert_profile_theme_preference(session: AsyncSession, user_id: int | str, color: str) -> str:
    uid = int(user_id)
    normalized_color = normalize_profile_theme_color(color)
    row = await session.get(User, uid)
    if row is not None:
        row.profile_theme_color = normalized_color
    return normalized_color
