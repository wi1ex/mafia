from __future__ import annotations
import json
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import TYPE_CHECKING, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
if TYPE_CHECKING:
    from ..models.game import GameScoringSettings

RATING_MODE = "rating"
DECISIVE_RESULTS = {"red", "black"}
RED_ROLES = {"citizen", "sheriff"}
BLACK_ROLES = {"mafia", "don"}
POINTS_QUANTUM = Decimal("0.01")
GAME_SCORING_RULES_VERSION = 1

GAME_SCORING_RULE_DEFAULTS: dict[str, Decimal] = {
    "fourth_foul": Decimal("-0.25"),
    "fourth_foul_lost": Decimal("-0.40"),
    "tech_foul": Decimal("-0.15"),
    "second_tech_foul_lost": Decimal("-0.35"),
    "suicide": Decimal("-0.30"),
    "suicide_lost": Decimal("-0.50"),
    "best_move_black_0": Decimal("-0.10"),
    "best_move_black_1": Decimal("0.00"),
    "best_move_black_2": Decimal("0.20"),
    "best_move_black_3": Decimal("0.40"),
}


def normalize_game_mode(raw: object) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    return RATING_MODE if str(raw or "").strip().lower() == RATING_MODE else "normal"


def normalize_game_points_value(raw: object) -> float:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0

    if not value.is_finite():
        return 0.0

    return float(value.quantize(POINTS_QUANTUM, rounding=ROUND_HALF_UP))


def _as_decimal(raw: object) -> Decimal | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None

    return value if value.is_finite() else None


def build_game_scoring_rules_snapshot(raw: Mapping[object, Any] | None = None) -> dict[str, float | int]:
    source = raw if isinstance(raw, Mapping) else {}
    snapshot: dict[str, float | int] = {"version": GAME_SCORING_RULES_VERSION}
    for key, default in GAME_SCORING_RULE_DEFAULTS.items():
        parsed = _as_decimal(source.get(key, default))
        value = default if parsed is None else parsed
        snapshot[key] = normalize_game_points_value(value)
    return snapshot


def parse_game_scoring_rules_snapshot(raw: object) -> dict[str, float | int] | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    if not isinstance(raw, Mapping):
        return None

    try:
        version = int(raw.get("version") or 0)
    except (TypeError, ValueError):
        return None

    if version != GAME_SCORING_RULES_VERSION:
        return None

    return build_game_scoring_rules_snapshot(raw)


async def ensure_game_scoring_settings(session: AsyncSession) -> GameScoringSettings:
    from ..models.game import GameScoringSettings

    row = await session.get(GameScoringSettings, 1)
    if row is None:
        row = GameScoringSettings(id=1, rules=build_game_scoring_rules_snapshot())
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            row = await session.get(GameScoringSettings, 1)
            if row is None:
                raise
        else:
            await session.refresh(row)

    normalized_rules = build_game_scoring_rules_snapshot(row.rules)
    if row.rules != normalized_rules:
        row.rules = normalized_rules
        await session.commit()
        await session.refresh(row)

    return row


async def get_game_scoring_rules_snapshot(session: AsyncSession) -> dict[str, float | int]:
    row = await ensure_game_scoring_settings(session)
    return build_game_scoring_rules_snapshot(row.rules)


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


def _action_user_id(action: Mapping[str, Any], key: str) -> int:
    try:
        user_id = int(action.get(key) or 0)
    except (TypeError, ValueError):
        return 0

    return user_id if user_id > 0 else 0


def _action_bool(action: Mapping[str, Any], key: str) -> bool:
    raw = action.get(key)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes"}

    return bool(raw)


def _is_black(role: str) -> bool:
    return role in BLACK_ROLES


def _apply_action_points(
    points: dict[int, Decimal],
    *,
    roles: Mapping[object, Any],
    actions: Iterable[Mapping[str, Any]],
    rules: Mapping[str, float | int],
) -> None:
    rule_values = {
        key: _as_decimal(rules.get(key)) or default
        for key, default in GAME_SCORING_RULE_DEFAULTS.items()
    }
    normalized_actions = [action for action in actions if isinstance(action, Mapping)]

    foul_loss_after: dict[int, bool] = {}
    for action in normalized_actions:
        if str(action.get("type") or "").strip().lower() != "death":
            continue
        if str(action.get("reason") or "").strip().lower() != "foul":
            continue
        target_id = _action_user_id(action, "target_id")
        if target_id in points:
            foul_loss_after[target_id] = (
                _action_bool(action, "game_lost_after") or _action_bool(action, "ppk")
            )

    for action in normalized_actions:
        action_type = str(action.get("type") or "").strip().lower()

        if action_type == "foul":
            target_id = _action_user_id(action, "target_id")
            try:
                count = int(action.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if target_id in points and count == 4:
                rule_key = "fourth_foul_lost" if foul_loss_after.get(target_id, False) else "fourth_foul"
                points[target_id] += rule_values[rule_key]
            continue

        if action_type == "tech_foul":
            target_id = _action_user_id(action, "target_id")
            try:
                count = int(action.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if target_id not in points or count not in (1, 2):
                continue
            rule_key = "second_tech_foul_lost" if count == 2 and foul_loss_after.get(target_id, False) else "tech_foul"
            points[target_id] += rule_values[rule_key]
            continue

        if action_type == "death":
            target_id = _action_user_id(action, "target_id")
            reason = str(action.get("reason") or "").strip().lower()
            if target_id in points and reason == "suicide":
                rule_key = "suicide_lost" if _action_bool(action, "game_lost_after") else "suicide"
                points[target_id] += rule_values[rule_key]
            continue

        if action_type != "best_move":
            continue

        actor_id = _action_user_id(action, "actor_id")
        if actor_id not in points or _role_for_user(roles, actor_id) not in RED_ROLES:
            continue

        targets_raw = action.get("targets")
        targets = targets_raw if isinstance(targets_raw, list) else []
        black_count = 0
        seen_target_ids: set[int] = set()
        for raw_target_id in targets:
            target_id = _action_user_id({"target_id": raw_target_id}, "target_id")
            if target_id <= 0 or target_id in seen_target_ids:
                continue
            seen_target_ids.add(target_id)
            if _is_black(_role_for_user(roles, target_id)):
                black_count += 1
        black_count = max(0, min(3, black_count))
        points[actor_id] += rule_values[f"best_move_black_{black_count}"]


def calculate_game_points(
    *,
    mode: object,
    result: object,
    roles: Mapping[object, Any],
    player_ids: Iterable[int | str],
    actions: Iterable[Mapping[str, Any]] | None = None,
    scoring_rules: Mapping[object, Any] | None = None,
) -> dict[str, float]:
    if normalize_game_mode(mode) != RATING_MODE:
        return {}

    players = _normalize_user_ids(player_ids)
    points = {user_id: Decimal("0") for user_id in players}
    normalized_result = str(result or "").strip().lower()

    if normalized_result in DECISIVE_RESULTS:
        for user_id in players:
            if _wins(_role_for_user(roles, user_id), normalized_result):
                points[user_id] = Decimal("1")

    active_rules = parse_game_scoring_rules_snapshot(scoring_rules)
    if active_rules is not None and actions is not None:
        _apply_action_points(points, roles=roles, actions=actions, rules=active_rules)

    return {str(user_id): normalize_game_points_value(value) for user_id, value in points.items()}
