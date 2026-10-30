from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Literal


MultiaccountKind = Literal["telegram", "browser", "ip"]
AUTH_ACTIONS = frozenset({"login", "register", "login_pwa", "register_pwa"})
MULTIACCOUNT_ACTIONS = AUTH_ACTIONS | {"telegram_verified"}
_MONTH_RE = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
_BROWSER_RE = re.compile(r"[0-9a-fA-F]{32}")
_TELEGRAM_RE = re.compile(r"(?:^|\s)tg_id=([0-9]+)(?=\s|$)")
_KIND_ORDER = {"telegram": 0, "browser": 1, "ip": 2}


def multiaccount_month_range(month: str) -> tuple[datetime, datetime]:
    if not _MONTH_RE.fullmatch(month):
        raise ValueError("invalid_month")

    year, number = map(int, month.split("-"))
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def log_identifiers(action: str, details: str) -> list[tuple[MultiaccountKind, str]]:
    if action == "telegram_verified":
        match = _TELEGRAM_RE.search(details)
        if match:
            raw = match[1].lstrip("0")
            if raw and len(raw) <= 19 and int(raw) <= 2**63 - 1:
                return [("telegram", raw)]

        return []

    if action not in AUTH_ACTIONS:
        return []

    metadata = {}
    for part in details.split("|")[1:]:
        key, separator, value = part.strip().partition("=")
        if separator and key in {"browser_id", "ip"}:
            metadata[key] = value.strip()

    identifiers: list[tuple[MultiaccountKind, str]] = []
    browser_id = metadata.get("browser_id", "")
    if _BROWSER_RE.fullmatch(browser_id):
        identifiers.append(("browser", browser_id.lower()))
    try:
        address = ip_address(metadata.get("ip", ""))
        address = getattr(address, "ipv4_mapped", None) or address
        identifiers.append(("ip", str(address)))
    except ValueError:
        pass

    return identifiers


@dataclass
class MultiaccountUserActivity:
    user_id: int
    events_count: int
    first_seen: datetime
    last_seen: datetime


@dataclass
class MultiaccountGroup:
    kind: MultiaccountKind
    value: str
    users: list[MultiaccountUserActivity]


class MultiaccountScan:
    def __init__(self, month: str):
        self.start, self.end = multiaccount_month_range(month)
        self.logs_scanned = 0
        self.usernames: dict[int, tuple[datetime, str | None]] = {}
        self._groups: dict[
            tuple[MultiaccountKind, str], dict[int, MultiaccountUserActivity]
        ] = {}

    def add_log(
        self, user_id: int | None, username: str | None, action: str,
        details: str, created_at: datetime,
    ) -> None:
        if action not in MULTIACCOUNT_ACTIONS or not user_id or user_id <= 0:
            return

        if not self.start <= created_at < self.end:
            return

        self.logs_scanned += 1
        previous = self.usernames.get(user_id)
        if previous is None or created_at >= previous[0]:
            self.usernames[user_id] = (created_at, username)

        for identifier in log_identifiers(action, details):
            users = self._groups.setdefault(identifier, {})
            activity = users.get(user_id)
            if activity is None:
                users[user_id] = MultiaccountUserActivity(user_id, 1, created_at, created_at)
            else:
                activity.events_count += 1
                activity.first_seen = min(activity.first_seen, created_at)
                activity.last_seen = max(activity.last_seen, created_at)

    def groups(self) -> list[MultiaccountGroup]:
        groups = [
            MultiaccountGroup(kind, value, sorted(users.values(), key=lambda user: user.user_id))
            for (kind, value), users in self._groups.items()
            if len(users) >= 2
        ]
        return sorted(groups, key=lambda group: (
            _KIND_ORDER[group.kind], -len(group.users), group.value,
        ))
