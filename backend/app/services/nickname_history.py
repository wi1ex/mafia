from __future__ import annotations
import json
from typing import Any, Iterable


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
