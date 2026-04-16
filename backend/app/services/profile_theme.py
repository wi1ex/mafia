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
PROFILE_THEME_ICON_NONE = "none"
PROFILE_THEME_ICON_COUNT = 29
PROFILE_THEME_ICONS: tuple[str, ...] = tuple(f"sub_icon{idx}" for idx in range(1, PROFILE_THEME_ICON_COUNT + 1))
PROFILE_THEME_ICON_DEFAULT = PROFILE_THEME_ICONS[0]
SUBSCRIPTION_END_LOCAL_HOUR = 2


@dataclass(slots=True)
class ProfileThemePreference:
    color: str | None = None
    icon: str | None = None


@dataclass(slots=True)
class ProfileThemeState:
    subscription_active: bool = False
    subscription_started_at: datetime | None = None
    subscription_until: datetime | None = None
    color: str | None = None
    icon: str | None = None


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


def normalize_optional_profile_theme_icon(raw: object) -> str | None:
    value = str(raw or "").strip().lower()
    if not value:
        return None

    if value == PROFILE_THEME_ICON_NONE:
        return PROFILE_THEME_ICON_NONE

    if value not in PROFILE_THEME_ICONS:
        raise ValueError("profile_theme_icon_invalid")

    return value


def normalize_profile_theme_icon(raw: object) -> str:
    normalized = normalize_optional_profile_theme_icon(raw)
    return normalized if normalized is not None else PROFILE_THEME_ICON_NONE


def _apply_profile_theme_defaults(row: User) -> bool:
    changed = False
    try:
        normalized_color = normalize_profile_theme_color(row.profile_theme_color)
    except ValueError:
        normalized_color = PROFILE_THEME_DEFAULT
    if row.profile_theme_color != normalized_color:
        row.profile_theme_color = normalized_color
        changed = True

    try:
        normalized_icon = normalize_optional_profile_theme_icon(row.profile_theme_icon)
    except ValueError:
        normalized_icon = None
    normalized_icon = normalized_icon or PROFILE_THEME_ICON_DEFAULT
    if row.profile_theme_icon != normalized_icon:
        row.profile_theme_icon = normalized_icon
        changed = True

    return changed


def shift_months(dt: datetime, months: int) -> datetime:
    months_i = int(months or 0)
    if months_i == 0:
        return dt

    month_index = (dt.month - 1) + months_i
    year = dt.year + (month_index // 12)
    month = (month_index % 12) + 1
    max_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, max_day)
    return dt.replace(year=year, month=month, day=day)


def add_months(dt: datetime, months: int) -> datetime:
    months_i = max(0, int(months or 0))
    if months_i <= 0:
        return dt

    return shift_months(dt, months_i)


def subtract_months(dt: datetime, months: int) -> datetime:
    months_i = max(0, int(months or 0))
    if months_i <= 0:
        return dt

    return shift_months(dt, -months_i)


def normalize_subscription_end_time(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(
            hour=SUBSCRIPTION_END_LOCAL_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )

    local_dt = dt.astimezone()
    rounded_local_dt = local_dt.replace(
        hour=SUBSCRIPTION_END_LOCAL_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )
    return rounded_local_dt.astimezone(dt.tzinfo)


def subscription_local_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt

    return dt.astimezone()


def restore_subscription_datetime_timezone(dt: datetime, source: datetime) -> datetime:
    if source.tzinfo is None:
        return dt

    return dt.astimezone(source.tzinfo)


def compute_subscription_end(starts_at: datetime, *, months: int = 0, days: int = 0) -> datetime:
    result = subscription_local_datetime(starts_at)
    if int(months or 0) > 0:
        result = add_months(result, int(months or 0))
    if int(days or 0) > 0:
        result = result + timedelta(days=int(days or 0))
    return restore_subscription_datetime_timezone(
        normalize_subscription_end_time(result),
        starts_at,
    )


def compute_subscription_reduced_end(ends_at: datetime, *, months: int = 0, days: int = 0) -> datetime:
    result = subscription_local_datetime(ends_at)
    if int(months or 0) > 0:
        result = subtract_months(result, int(months or 0))
    if int(days or 0) > 0:
        result = result - timedelta(days=int(days or 0))

    return restore_subscription_datetime_timezone(
        normalize_subscription_end_time(result),
        ends_at,
    )


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


async def fetch_profile_theme_preferences(session: AsyncSession, user_ids: Iterable[int | str]) -> dict[int, ProfileThemePreference]:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return {}

    rows = await session.execute(
        select(User.id, User.profile_theme_color, User.profile_theme_icon).where(User.id.in_(ids))
    )
    out: dict[int, ProfileThemePreference] = {}
    for user_id_raw, color_raw, icon_raw in rows.all():
        try:
            uid = int(user_id_raw)
        except Exception:
            continue
        pref = ProfileThemePreference()
        try:
            pref.color = normalize_profile_theme_color(color_raw)
        except ValueError:
            pass
        try:
            pref.icon = normalize_optional_profile_theme_icon(icon_raw)
        except ValueError:
            pass
        out[uid] = pref
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
        preference = preferences.get(uid) or ProfileThemePreference()
        out[uid] = ProfileThemeState(
            subscription_active=True,
            subscription_started_at=subscription.starts_at,
            subscription_until=subscription.ends_at,
            color=preference.color or PROFILE_THEME_DEFAULT,
            icon=preference.icon or PROFILE_THEME_ICON_DEFAULT,
        )
    return out


async def resolve_profile_theme_state(session: AsyncSession, user_id: int | str, *, now: datetime | None = None) -> ProfileThemeState:
    uid = int(user_id)
    states = await resolve_profile_theme_states(session, [uid], now=now)
    return states.get(uid) or ProfileThemeState()


async def ensure_profile_theme_defaults(session: AsyncSession, user_id: int | str, *, now: datetime | None = None) -> bool:
    uid = int(user_id)
    current = now or datetime.now(timezone.utc)
    active_subscription = await session.scalar(
        select(UserSubscription.user_id)
        .where(
            UserSubscription.user_id == uid,
            UserSubscription.starts_at <= current,
            UserSubscription.ends_at > current,
        )
        .limit(1)
    )
    if active_subscription is None:
        return False

    row = await session.get(User, uid)
    if row is None:
        return False

    return _apply_profile_theme_defaults(row)


async def upsert_profile_theme_preference(session: AsyncSession, user_id: int | str, color: str) -> str:
    uid = int(user_id)
    normalized_color = normalize_profile_theme_color(color)
    row = await session.get(User, uid)
    if row is not None:
        row.profile_theme_color = normalized_color
    return normalized_color


async def upsert_profile_theme_icon_preference(session: AsyncSession, user_id: int | str, icon: object) -> str | None:
    uid = int(user_id)
    normalized_icon = normalize_optional_profile_theme_icon(icon)
    row = await session.get(User, uid)
    if row is not None:
        row.profile_theme_icon = normalized_icon
    return normalized_icon
