from __future__ import annotations
from collections.abc import Iterable, Mapping
from typing import Any

RATING_MODE = "rating"
DECISIVE_RESULTS = {"red", "black"}
RED_ROLES = {"citizen", "sheriff"}
BLACK_ROLES = {"mafia", "don"}


def normalize_game_mode(raw: object) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    return RATING_MODE if str(raw or "").strip().lower() == RATING_MODE else "normal"


def _normalize_user_ids(player_ids: Iterable[int | str]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for raw_user_id in player_ids:
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        result.append(user_id)
    return result


def _role_for_user(roles: Mapping[object, Any], user_id: int) -> str:
    raw_role = roles.get(str(user_id), roles.get(user_id, ""))
    if isinstance(raw_role, bytes):
        raw_role = raw_role.decode("utf-8", "ignore")
    return str(raw_role or "").strip().lower()


def _wins(role: str, result: str) -> bool:
    if result == "red":
        return role in RED_ROLES

    if result == "black":
        return role in BLACK_ROLES

    return False


def calculate_game_points(
    *,
    mode: object,
    result: object,
    roles: Mapping[object, Any],
    player_ids: Iterable[int | str],
    actions: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, int]:
    """Calculate and persist each player's total points for one finished game.

    The result is intentionally calculated from immutable game snapshots.  Future
    bonuses and penalties belong here and can use ``actions`` without changing the
    end-of-game flow or the storage format used by game history.
    """
    del actions  # Reserved for the next scoring rules.

    if normalize_game_mode(mode) != RATING_MODE:
        return {}

    players = _normalize_user_ids(player_ids)
    points = {str(user_id): 0 for user_id in players}
    normalized_result = str(result or "").strip().lower()

    if normalized_result not in DECISIVE_RESULTS:
        return points

    for user_id in players:
        if _wins(_role_for_user(roles, user_id), normalized_result):
            points[str(user_id)] = 1

    return points
