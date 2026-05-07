from __future__ import annotations
import json
import re
from typing import Any, Iterable
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from ..models.log import AppLog
from ..models.user import User

USERNAME_UPDATED_RE = re.compile(r":\s*(?P<old>.+?)\s*->\s*(?P<new>.+?)\s*$")
ADMIN_RESET_RE = re.compile(r"user_id=(?P<user_id>\d+)\s+from=(?P<old>\S+)\s+to=(?P<new>\S+)")


# AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
async def ensure_nickname_history_storage(conn: AsyncConnection) -> None:
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS nickname_history TEXT"))
# AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA


def normalize_nickname_history(raw: Any) -> list[str]:
    if raw is None:
        return []

    text_value = str(raw or "").strip()
    if not text_value:
        return []

    parsed: Any
    try:
        parsed = json.loads(text_value)
    except Exception:
        parsed = [part.strip() for part in text_value.splitlines()]

    if not isinstance(parsed, list):
        return []

    return unique_nicknames(parsed)


def unique_nicknames(items: Iterable[Any], *, exclude: Iterable[Any] = ()) -> list[str]:
    excluded = {str(item or "").strip().casefold() for item in exclude if str(item or "").strip()}
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in excluded or key in seen:
            continue
        seen.add(key)
        out.append(name)

    return out


def serialize_nickname_history(items: Iterable[Any]) -> str:
    return json.dumps(unique_nicknames(items), ensure_ascii=False, separators=(",", ":"))


def prepend_nickname_history(raw: Any, nickname: Any, *, current_username: Any = None) -> str:
    name = str(nickname or "").strip()
    existing = normalize_nickname_history(raw)
    if not name:
        return serialize_nickname_history(existing)

    return serialize_nickname_history(unique_nicknames([name, *existing], exclude=[current_username]))


def build_nickname_history_out(current_username: Any, raw_history: Any) -> list[str]:
    current = str(current_username or "").strip()
    old_items = unique_nicknames(normalize_nickname_history(raw_history), exclude=[current])
    return [current, *old_items] if current else old_items


def _prepend_unique(items: list[str], nickname: str, *, current_username: str | None = None) -> None:
    normalized = str(nickname or "").strip()
    if not normalized:
        return

    current_key = str(current_username or "").strip().casefold()
    key = normalized.casefold()
    if current_key and key == current_key:
        return

    items[:] = [item for item in items if item.casefold() != key]
    items.insert(0, normalized)


def _parse_log_change(row: tuple[Any, Any, Any, Any, Any]) -> tuple[int, str] | None:
    log_id, user_id, action, details, _created_at = row
    action_value = str(action or "").strip()
    details_value = str(details or "").strip()

    if action_value == "username_updated":
        match = USERNAME_UPDATED_RE.search(details_value)
        if not match:
            return None

        try:
            uid = int(user_id or 0)
        except Exception:
            uid = 0
        old_username = match.group("old").strip()
        return (uid, old_username) if uid > 0 and old_username else None

    if action_value == "admin_nickname_reset":
        match = ADMIN_RESET_RE.search(details_value)
        if not match:
            return None

        try:
            uid = int(match.group("user_id") or 0)
        except Exception:
            uid = 0
        old_username = match.group("old").strip()
        return (uid, old_username) if uid > 0 and old_username else None

    _ = log_id
    return None


async def backfill_nickname_history_from_logs(session: AsyncSession) -> int:
    target_rows = await session.execute(
        select(User.id, User.username)
        .where(User.nickname_history.is_(None))
    )
    targets = {int(uid): str(username or "") for uid, username in target_rows.all()}
    if not targets:
        return 0

    histories: dict[int, list[str]] = {uid: [] for uid in targets}
    log_rows = await session.execute(
        select(AppLog.id, AppLog.user_id, AppLog.action, AppLog.details, AppLog.created_at)
        .where(AppLog.action.in_(["username_updated", "admin_nickname_reset"]))
        .order_by(AppLog.created_at.asc(), AppLog.id.asc())
    )

    for row in log_rows.all():
        parsed = _parse_log_change(row)
        if not parsed:
            continue
        uid, old_username = parsed
        if uid not in histories:
            continue
        _prepend_unique(histories[uid], old_username, current_username=targets.get(uid))

    changed = 0
    for uid, current_username in targets.items():
        value = serialize_nickname_history(unique_nicknames(histories.get(uid, []), exclude=[current_username]))
        await session.execute(
            update(User)
            .where(User.id == uid, User.nickname_history.is_(None))
            .values(nickname_history=value)
        )
        changed += 1

    await session.commit()
    return changed
