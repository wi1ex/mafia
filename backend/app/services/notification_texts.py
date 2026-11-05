from __future__ import annotations
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SUBSCRIPTION_EXPIRING_SOON_NOTICE_BEFORE = timedelta(days=3)


def _subscription_datetime_as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)

def _subscription_expiry_matches(actual: datetime, expected: datetime, now: datetime) -> bool:
    actual_utc = _subscription_datetime_as_utc(actual)
    return actual_utc == _subscription_datetime_as_utc(expected) and actual_utc <= _subscription_datetime_as_utc(now)

def _subscription_expiring_soon_notice_window(now: datetime) -> tuple[datetime, datetime]:
    local_now = _subscription_datetime_as_utc(now).astimezone(ZoneInfo("Europe/Moscow"))
    target_start_local = (
        local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        + SUBSCRIPTION_EXPIRING_SOON_NOTICE_BEFORE
    )
    target_end_local = target_start_local + timedelta(days=1)
    return target_start_local.astimezone(timezone.utc), target_end_local.astimezone(timezone.utc)

def format_subscription_until(ends_at: datetime) -> str:
    local_dt = _subscription_datetime_as_utc(ends_at).astimezone(ZoneInfo("Europe/Moscow"))
    return local_dt.strftime("%d.%m.%Y в %H:%M МСК")

def _ru_plural(value: int, one: str, few: str, many: str) -> str:
    number = abs(int(value))
    if 11 <= number % 100 <= 14:
        return many

    last_digit = number % 10
    if last_digit == 1:
        return one

    if 2 <= last_digit <= 4:
        return few

    return many

def format_subscription_purchase_duration(*, months: int = 0, days: int = 0) -> str:
    parts: list[str] = []
    months_value = max(0, int(months or 0))
    days_value = max(0, int(days or 0))
    years_value, months_value = divmod(months_value, 12)
    if years_value:
        parts.append(f"{years_value} {_ru_plural(years_value, 'год', 'года', 'лет')}")
    if months_value:
        parts.append(
            f"{months_value} "
            f"{_ru_plural(months_value, 'месяц', 'месяца', 'месяцев')}"
        )
    if days_value:
        parts.append(
            f"{days_value} "
            f"{_ru_plural(days_value, 'день', 'дня', 'дней')}"
        )

    return " ".join(parts) or "выбранный срок"

def _split_admin_telegram_text(text: str, *, context: str | None = None) -> list[str]:
    if len(text.encode("utf-16-le")) // 2 <= 4096:
        return [text]

    chunks: list[str] = []
    start = 0
    units = 0
    for index, char in enumerate(text):
        char_units = 2 if ord(char) > 0xFFFF else 1
        if units + char_units > 3500:
            chunks.append(text[start:index])
            start = index
            units = 0
        units += char_units
    chunks.append(text[start:])
    label = str(context or "Сообщение администратору").strip()[:160]
    total = len(chunks)
    return [f"{label} · часть {index}/{total}\n\n{chunk}" for index, chunk in enumerate(chunks, 1)]

def _subscription_notice_event_key(user_id: int, ends_at: datetime, *, event: str) -> str:
    return f"subscription:{event}:{int(user_id)}:{_subscription_datetime_as_utc(ends_at).isoformat()}"
