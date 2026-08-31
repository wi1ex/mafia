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
GAME_SCORING_RULES_VERSION = 3
LEGACY_GAME_SCORING_RULES_VERSIONS = frozenset({1, 2})

GAME_SCORING_RULE_DEFAULTS: dict[str, Decimal] = {
    "additional_points_min": Decimal("-1.00"),
    "additional_points_max": Decimal("1.00"),
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
    "night_shoot_miss": Decimal("-0.20"),
    "night_shoot_miss_terminal": Decimal("-0.50"),
    "vote_opponent_team": Decimal("0.10"),
    "vote_red_terminal": Decimal("-0.20"),
    "vote_red_terminal_3v3": Decimal("-0.30"),
    "black_win_3v3": Decimal("0.30"),
    "vote_lift_same_team": Decimal("-0.30"),
    "vote_lift_opponent_team": Decimal("0.30"),
    "black_day_under_seven": Decimal("0.10"),
}

NEW_ACTION_RULE_KEYS = frozenset({
    "night_shoot_miss",
    "night_shoot_miss_terminal",
    "vote_opponent_team",
    "vote_red_terminal",
    "vote_red_terminal_3v3",
    "black_win_3v3",
    "vote_lift_same_team",
    "vote_lift_opponent_team",
    "black_day_under_seven",
})


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

    if version == GAME_SCORING_RULES_VERSION:
        return build_game_scoring_rules_snapshot(raw)

    if version not in LEGACY_GAME_SCORING_RULES_VERSIONS:
        return None

    legacy_snapshot = build_game_scoring_rules_snapshot(raw)
    legacy_snapshot["version"] = version
    if version == 1:
        for key in NEW_ACTION_RULE_KEYS:
            legacy_snapshot[key] = 0.0
    return legacy_snapshot


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


def _action_user_ids(action: Mapping[str, Any], key: str) -> list[int]:
    raw_items = action.get(key)
    if not isinstance(raw_items, (list, tuple, set)):
        return []

    user_ids: list[int] = []
    seen: set[int] = set()
    for raw_user_id in raw_items:
        user_id = _action_user_id({"user_id": raw_user_id}, "user_id")
        if user_id <= 0 or user_id in seen:
            continue
        seen.add(user_id)
        user_ids.append(user_id)
    return user_ids


def _action_bool(action: Mapping[str, Any], key: str) -> bool:
    raw = action.get(key)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes"}

    return bool(raw)


def _is_black(role: str) -> bool:
    return role in BLACK_ROLES


def _team_for_role(role: str) -> str:
    if role in RED_ROLES:
        return "red"

    if role in BLACK_ROLES:
        return "black"

    return ""


def _apply_action_points(
    points: dict[int, Decimal],
    *,
    roles: Mapping[object, Any],
    actions: Iterable[Mapping[str, Any]],
    rules: Mapping[str, float | int],
) -> None:
    rule_values: dict[str, Decimal] = {}
    for key, default in GAME_SCORING_RULE_DEFAULTS.items():
        parsed = _as_decimal(rules.get(key))
        rule_values[key] = default if parsed is None else parsed
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

        if action_type == "night_shoot_result":
            if _action_bool(action, "kill_ok"):
                continue

            shooters = [
                user_id
                for user_id in _action_user_ids(action, "shooters")
                if user_id in points and _is_black(_role_for_user(roles, user_id))
            ]
            if len(shooters) not in (1, 2, 3):
                continue

            terminal_miss = _action_bool(action, "black_wins_if_kill")
            if len(shooters) in (1, 2):
                if terminal_miss:
                    for shooter_id in shooters:
                        points[shooter_id] += rule_values["night_shoot_miss_terminal"]
                continue

            shots_raw = action.get("shots")
            shots = shots_raw if isinstance(shots_raw, Mapping) else {}
            target_counts: dict[int, int] = {}
            shot_by_shooter: dict[int, int] = {}
            for shooter_id in shooters:
                target_id = _action_user_id(
                    {"target_id": shots.get(str(shooter_id), shots.get(shooter_id, 0))},
                    "target_id",
                )
                shot_by_shooter[shooter_id] = target_id
                if target_id > 0:
                    target_counts[target_id] = target_counts.get(target_id, 0) + 1

            majority_targets = [target_id for target_id, count in target_counts.items() if count == 2]
            if len(majority_targets) != 1:
                continue

            majority_target = majority_targets[0]
            missers = [shooter_id for shooter_id, target_id in shot_by_shooter.items() if target_id != majority_target]
            if len(missers) != 1:
                continue

            rule_key = "night_shoot_miss_terminal" if terminal_miss else "night_shoot_miss"
            points[missers[0]] += rule_values[rule_key]
            continue

        if action_type == "vote" and _action_bool(action, "lift"):
            if not _action_bool(action, "passed"):
                continue

            target_ids = _action_user_ids(action, "targets")
            if len(target_ids) < 2:
                continue

            target_teams = {_team_for_role(_role_for_user(roles, target_id)) for target_id in target_ids}
            if "" in target_teams or len(target_teams) != 1:
                continue

            target_team = next(iter(target_teams))
            for voter_id in _action_user_ids(action, "by"):
                if voter_id not in points:
                    continue
                voter_team = _team_for_role(_role_for_user(roles, voter_id))
                if not voter_team:
                    continue
                rule_key = "vote_lift_same_team" if voter_team == target_team else "vote_lift_opponent_team"
                points[voter_id] += rule_values[rule_key]
            continue

        if action_type == "vote":
            leaders = _action_user_ids(action, "leaders")
            if not _action_bool(action, "will_eliminate") or len(leaders) != 1:
                continue

            target_id = leaders[0]
            target_team = _team_for_role(_role_for_user(roles, target_id))
            votes_raw = action.get("votes")
            votes = votes_raw if isinstance(votes_raw, Mapping) else {}
            voters = _action_user_ids(
                {"by": votes.get(str(target_id), votes.get(target_id, []))},
                "by",
            )
            if target_team:
                for voter_id in voters:
                    if voter_id not in points:
                        continue
                    voter_team = _team_for_role(_role_for_user(roles, voter_id))
                    if voter_team and voter_team != target_team:
                        points[voter_id] += rule_values["vote_opponent_team"]
            continue

        if action_type == "day_start":
            alive_ids = _action_user_ids(action, "alive")
            if len(alive_ids) >= 7:
                continue
            for user_id in alive_ids:
                if user_id in points and _is_black(_role_for_user(roles, user_id)):
                    points[user_id] += rule_values["black_day_under_seven"]
            continue

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

            if (
                reason == "vote"
                and _action_bool(action, "vote_unique")
                and not _action_bool(action, "vote_lift")
                and target_id in points
            ):
                target_team = _team_for_role(_role_for_user(roles, target_id))
                voters = [voter_id for voter_id in _action_user_ids(action, "by") if voter_id in points]
                result_after = str(action.get("result_after") or "").strip().lower()
                if target_team == "red" and result_after == "black":
                    red_alive_after = _action_user_id(action, "red_alive_after")
                    black_alive_after = _action_user_id(action, "black_alive_after")
                    is_black_win_3v3 = red_alive_after == 3 and black_alive_after == 3
                    penalty_key = "vote_red_terminal_3v3" if is_black_win_3v3 else "vote_red_terminal"
                    for voter_id in voters:
                        if _team_for_role(_role_for_user(roles, voter_id)) == "red":
                            points[voter_id] += rule_values[penalty_key]
                    if is_black_win_3v3:
                        for user_id in points:
                            if _is_black(_role_for_user(roles, user_id)):
                                points[user_id] += rule_values["black_win_3v3"]
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


def _additional_points_bounds(rules: Mapping[str, float | int]) -> tuple[Decimal, Decimal]:
    lower = _as_decimal(rules.get("additional_points_min"))
    upper = _as_decimal(rules.get("additional_points_max"))
    if lower is None:
        lower = GAME_SCORING_RULE_DEFAULTS["additional_points_min"]
    if upper is None:
        upper = GAME_SCORING_RULE_DEFAULTS["additional_points_max"]
    return (lower, upper) if lower <= upper else (upper, lower)


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
    base_points = {user_id: Decimal("0") for user_id in players}
    normalized_result = str(result or "").strip().lower()

    if normalized_result in DECISIVE_RESULTS:
        for user_id in players:
            if _wins(_role_for_user(roles, user_id), normalized_result):
                base_points[user_id] = Decimal("1")

    active_rules = parse_game_scoring_rules_snapshot(scoring_rules)
    if active_rules is not None and actions is not None:
        additional_points = {user_id: Decimal("0") for user_id in players}
        _apply_action_points(additional_points, roles=roles, actions=actions, rules=active_rules)
        additional_min, additional_max = _additional_points_bounds(active_rules)
        for user_id, value in additional_points.items():
            base_points[user_id] += min(max(value, additional_min), additional_max)

    return {str(user_id): normalize_game_points_value(value) for user_id, value in base_points.items()}
