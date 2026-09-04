from __future__ import annotations
import json
from collections.abc import Callable, Iterable, Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import combinations
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

GAME_SCORING_RULE_DEFAULTS: dict[str, Decimal] = {
    "additional_points_min": Decimal("-1.00"),
    "additional_points_max": Decimal("1.00"),
    "fourth_foul": Decimal("-0.30"),
    "fourth_foul_lost": Decimal("-0.50"),
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
    "nomination_black_prevents_black_win": Decimal("-0.50"),
    "nomination_red_last_hope": Decimal("0.30"),
    "sheriff_two_unobvious_black_checks": Decimal("0.20"),
    "don_missed_sheriff_two_checks": Decimal("-0.10"),
    "citizen_false_check": Decimal("-0.10"),
    "sheriff_false_check_black_win": Decimal("-0.50"),
    "black_day_under_seven": Decimal("0.10"),
    "night_opinion_correct": Decimal("0.10"),
    "night_opinion_wrong": Decimal("-0.10"),
    "farewell_red_correct": Decimal("0.15"),
    "farewell_red_wrong": Decimal("-0.20"),
    "farewell_black_correct": Decimal("0.20"),
    "farewell_black_wrong": Decimal("-0.25"),
    "farewell_black_named_red": Decimal("0.10"),
    "farewell_claimant_black_named_red": Decimal("0.15"),
}

GAME_SCORING_LABEL_DEFAULTS: dict[str, str] = {
    "fourth_foul": "Удаление по фолам",
    "fourth_foul_lost": "Удаление по фолам на поражение",
    "tech_foul": "{count}-й тех. фол",
    "second_tech_foul_lost": "Удаление по тех. фолам на поражение",
    "suicide": "Самоубийство",
    "suicide_lost": "Самоубийство на поражение",
    "best_move_black_0": "Лучший ход: 0 из 3",
    "best_move_black_1": "Лучший ход: 1 из 3",
    "best_move_black_2": "Лучший ход: 2 из 3",
    "best_move_black_3": "Лучший ход: 3 из 3",
    "night_shoot_miss": "Промахнувшийся черный",
    "night_shoot_miss_terminal": "Промах при гарантированной победе",
    "vote_opponent_team": "Заголосовал игрока другой команды",
    "vote_red_terminal": "Голосование на поражение",
    "vote_red_terminal_3v3": "Голосование на 3в3",
    "black_win_3v3": "Победа 3в3",
    "vote_lift_same_team": "Подъём игроков своей команды",
    "vote_lift_opponent_team": "Подъём игроков другой команды",
    "nomination_black_prevents_black_win": "Выставление при гарантированной победе",
    "nomination_red_last_hope": "Последняя надежда",
    "sheriff_two_unobvious_black_checks": "Две подряд чёрные проверки",
    "don_missed_sheriff_two_checks": "Не нашёл шерифа за две проверки",
    "citizen_false_check": "Ложная проверка будучи мирным",
    "sheriff_false_check_black_win": "Ложная проверка шерифа при победе чёрных",
    "black_day_under_seven": "Проход в круг при 3-6х",
    "night_opinion_correct": "Ночное мнение: верный цвет",
    "night_opinion_wrong": "Ночное мнение: неверный цвет",
    "farewell_red_correct": "Завещание: верно указан красный",
    "farewell_red_wrong": "Завещание: красный указан чёрным",
    "farewell_black_correct": "Завещание: верно указан чёрный",
    "farewell_black_wrong": "Завещание: чёрный указан красным",
    "farewell_black_named_red": "Оставлен красным",
    "farewell_claimant_black_named_red": "Оставлен приоритетной версией",
}


def normalize_game_mode(raw: object) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    return RATING_MODE if str(raw or "").strip().lower() == RATING_MODE else "normal"


def can_set_game_mode(mode: object, *, rating_mode_eligible: object) -> bool:
    return normalize_game_mode(mode) != RATING_MODE or bool(rating_mode_eligible)


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


def _normalize_scoring_label(raw: object, default: str) -> str:
    if not isinstance(raw, str):
        return default

    value = raw.strip()
    return value[:255] if value else default


def build_game_scoring_rules_snapshot(raw: Mapping[object, Any] | None = None) -> dict[str, float | str]:
    source = raw if isinstance(raw, Mapping) else {}
    snapshot: dict[str, float | str] = {}
    for key, default in GAME_SCORING_RULE_DEFAULTS.items():
        parsed = _as_decimal(source.get(key, default))
        value = default if parsed is None else parsed
        snapshot[key] = normalize_game_points_value(value)
    for key, default in GAME_SCORING_LABEL_DEFAULTS.items():
        snapshot[f"{key}_label"] = _normalize_scoring_label(source.get(f"{key}_label"), default)
    return snapshot


def parse_game_scoring_rules_snapshot(raw: object) -> dict[str, float | str] | None:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    if not isinstance(raw, Mapping) or not raw:
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


async def get_game_scoring_rules_snapshot(session: AsyncSession) -> dict[str, float | str]:
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


def _record_scoring_adjustment(
        breakdown: dict[int, list[dict[str, Any]]] | None,
        *,
        user_id: int,
        rule_key: str,
        label: str,
        value: Decimal,
) -> None:
    if breakdown is None:
        return

    breakdown.setdefault(user_id, []).append(
        {
            "rule_key": rule_key,
            "label": label,
            "points": normalize_game_points_value(value),
        }
    )


def _scoring_rule_label(
        rules: Mapping[str, object],
        rule_key: str,
        **placeholders: object,
) -> str:
    default = GAME_SCORING_LABEL_DEFAULTS[rule_key]
    label = _normalize_scoring_label(rules.get(f"{rule_key}_label"), default)
    for key, value in placeholders.items():
        label = label.replace(f"{{{key}}}", str(value))
    return label


def _action_type(action: Mapping[str, Any]) -> str:
    return str(action.get("type") or "").strip().lower()


def _normalize_action_versions(raw: object, player_ids: set[int]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    versions: list[dict[str, Any]] = []
    claimant_ids: set[int] = set()
    for raw_version in raw:
        if not isinstance(raw_version, Mapping):
            continue
        claimant_id = _action_user_id(raw_version, "claimant_id")
        if claimant_id not in player_ids or claimant_id in claimant_ids:
            continue

        raw_checks = raw_version.get("checks")
        if not isinstance(raw_checks, list):
            continue

        checks: list[dict[str, Any]] = []
        checked_ids: set[int] = set()
        for raw_check in raw_checks:
            if not isinstance(raw_check, Mapping):
                continue
            target_id = _action_user_id(raw_check, "target_id")
            verdict = str(raw_check.get("verdict") or "").strip().lower()
            if (
                    target_id not in player_ids
                    or target_id == claimant_id
                    or target_id in checked_ids
                    or verdict not in {"red", "black"}
            ):
                continue
            checked_ids.add(target_id)
            checks.append({"target_id": target_id, "verdict": verdict})

        if not checks:
            continue
        claimant_ids.add(claimant_id)
        versions.append({"claimant_id": claimant_id, "checks": checks})

    return versions


def _set_fixed_color(colors: dict[int, str], user_id: int, color: str) -> bool:
    existing = colors.get(user_id)
    if existing is not None and existing != color:
        return False

    colors[user_id] = color
    return True


def _candidate_fixed_colors(
        version: Mapping[str, Any],
        active_versions: Iterable[Mapping[str, Any]],
        *,
        player_ids: set[int],
        private_colors: Mapping[int, str],
        proxy_claimant_id: int = 0,
) -> dict[int, str] | None:
    claimant_id = _action_user_id(version, "claimant_id")
    if claimant_id not in player_ids:
        return None

    colors: dict[int, str] = {}
    if not _set_fixed_color(colors, claimant_id, "red"):
        return None

    for other_version in active_versions:
        other_claimant_id = _action_user_id(other_version, "claimant_id")
        if other_claimant_id and other_claimant_id != claimant_id:
            if other_claimant_id == proxy_claimant_id:
                continue
            if (
                    other_claimant_id not in player_ids
                    or not _set_fixed_color(colors, other_claimant_id, "black")
            ):
                return None

    raw_checks = version.get("checks")
    if not isinstance(raw_checks, list):
        return None

    for raw_check in raw_checks:
        if not isinstance(raw_check, Mapping):
            return None

        target_id = _action_user_id(raw_check, "target_id")
        verdict = str(raw_check.get("verdict") or "").strip().lower()
        if target_id not in player_ids or verdict not in {"red", "black"}:
            return None

        if not _set_fixed_color(colors, target_id, verdict):
            return None

    for user_id, color in private_colors.items():
        if user_id not in player_ids or color not in {"red", "black"}:
            continue
        if not _set_fixed_color(colors, user_id, color):
            return None

    return colors


def _candidate_black_teams(
        fixed_colors: Mapping[int, str],
        *,
        player_ids: set[int],
        alive_states: Iterable[frozenset[int]],
) -> list[frozenset[int]]:
    black_ids = {user_id for user_id, color in fixed_colors.items() if color == "black"}
    red_ids = {user_id for user_id, color in fixed_colors.items() if color == "red"}
    if len(black_ids) > 3 or black_ids & red_ids:
        return []

    missing_black_count = 3 - len(black_ids)
    candidates = sorted(player_ids - black_ids - red_ids)
    if missing_black_count < 0 or len(candidates) < missing_black_count:
        return []

    compatible_teams: list[frozenset[int]] = []
    for additional_black_ids in combinations(candidates, missing_black_count):
        black_team = frozenset(black_ids | set(additional_black_ids))
        if any(
                not _alive_state_can_continue(alive_ids, black_team)
                for alive_ids in alive_states
        ):
            continue
        compatible_teams.append(black_team)
    return compatible_teams


def _alive_state_can_continue(alive_ids: frozenset[int], black_team: frozenset[int]) -> bool:
    black_alive = len(alive_ids & black_team)
    red_alive = len(alive_ids) - black_alive
    return 0 < black_alive < red_alive


def _night_opinion_guess_side(raw: object) -> str:
    if isinstance(raw, Mapping):
        raw = raw.get("guess")
    value = str(raw or "").strip().lower()
    if value in {"citizen", "red"}:
        return "red"

    if value in {"mafia", "black"}:
        return "black"

    return ""


def _night_opinion_obvious_colors(
        *,
        actor_id: int,
        roles: Mapping[object, Any],
        player_ids: set[int],
        active_versions: list[dict[str, Any]],
        sheriff_checks: Mapping[int, set[int]],
        alive_states: Iterable[frozenset[int]],
        sources: dict[int, str] | None = None,
) -> dict[int, str]:
    actor_role = _role_for_user(roles, actor_id)
    if actor_role not in RED_ROLES or actor_id not in player_ids:
        return {}

    claimant_ids = {_action_user_id(version, "claimant_id") for version in active_versions}
    claimant_ids.discard(0)
    is_citizen_proxy_author = actor_role == "citizen" and actor_id in claimant_ids
    explicitly_black_checked = any(
        _action_user_id(check, "target_id") == actor_id
        and str(check.get("verdict") or "").strip().lower() == "black"
        for version in active_versions
        for check in (version.get("checks") if isinstance(version.get("checks"), list) else [])
        if isinstance(check, Mapping)
    )

    private_colors: dict[int, str] = {actor_id: "red"}
    known_color_sources: dict[int, str] = {actor_id: "собственная роль"}
    if actor_role == "sheriff":
        for target_id in sheriff_checks.get(actor_id, set()):
            target_color = _team_for_role(_role_for_user(roles, target_id))
            if target_color:
                private_colors[target_id] = target_color
                known_color_sources[target_id] = "личная проверка шерифа"

    frozen_alive_states = tuple(alive_states)
    known_colors: dict[int, str] = dict(private_colors)

    def set_known_color(user_id: int, color: str, source: str) -> None:
        if user_id in known_colors:
            return

        known_colors[user_id] = color
        known_color_sources[user_id] = source

    if actor_role == "sheriff":
        counterclaim_ids = claimant_ids - {actor_id}
        unresolved_counterclaim_ids = counterclaim_ids - set(private_colors)
        private_black_check_count = sum(
            color == "black"
            for user_id, color in private_colors.items()
            if user_id != actor_id
        )
        remaining_black_slots = 3 - private_black_check_count

        if remaining_black_slots <= 0:
            for claimant_id in unresolved_counterclaim_ids:
                set_known_color(
                    claimant_id,
                    "red",
                    "чёрная тройка собрана личными проверками шерифа",
                )
        elif len(unresolved_counterclaim_ids) <= remaining_black_slots:
            for claimant_id in unresolved_counterclaim_ids:
                set_known_color(
                    claimant_id,
                    "black",
                    "контрвскрытие заполняет место чёрной тройки",
                )

        sheriff_black_teams = _candidate_black_teams(
            known_colors,
            player_ids=player_ids,
            alive_states=frozen_alive_states,
        )
        if len(unresolved_counterclaim_ids) > remaining_black_slots > 0:
            sheriff_black_teams = [
                black_team
                for black_team in sheriff_black_teams
                if len(black_team & unresolved_counterclaim_ids) == remaining_black_slots
            ]

        for user_id in player_ids:
            is_black = [user_id in black_team for black_team in sheriff_black_teams]
            if is_black and all(is_black):
                set_known_color(
                    user_id,
                    "black",
                    "личные проверки шерифа и состав живых игроков",
                )
            elif sheriff_black_teams and not any(is_black):
                set_known_color(
                    user_id,
                    "red",
                    "личные проверки шерифа и состав живых игроков",
                )

        known_black_ids = {
            user_id for user_id, color in known_colors.items() if color == "black"
        }
        if len(known_black_ids) == 3:
            for user_id in player_ids:
                set_known_color(
                    user_id,
                    "black" if user_id in known_black_ids else "red",
                    "три известных чёрных образуют чёрную тройку",
                )
        if sources is not None:
            sources.update(known_color_sources)
        return known_colors

    if len(claimant_ids) >= 4:
        for user_id in player_ids - claimant_ids:
            if user_id not in known_colors:
                known_colors[user_id] = "red"
                known_color_sources[user_id] = "четыре или больше активных вскрытий"
        if sources is not None:
            sources.update(known_color_sources)
        return known_colors

    if is_citizen_proxy_author and len(active_versions) > 1 and not explicitly_black_checked:
        own_version = next(
            (
                version
                for version in active_versions
                if _action_user_id(version, "claimant_id") == actor_id
            ),
            None,
        )
        if own_version is not None:
            own_fixed_colors = _candidate_fixed_colors(
                own_version,
                active_versions,
                player_ids=player_ids,
                private_colors=private_colors,
            )
            if own_fixed_colors is not None and _candidate_black_teams(
                    own_fixed_colors,
                    player_ids=player_ids,
                    alive_states=frozen_alive_states,
            ):
                return {}

    false_claimant_ids: set[int] = set()
    possible_black_teams: list[frozenset[int]] = []
    for version in active_versions:
        claimant_id = _action_user_id(version, "claimant_id")
        fixed_colors = _candidate_fixed_colors(
            version,
            active_versions,
            player_ids=player_ids,
            private_colors=private_colors,
            proxy_claimant_id=actor_id if is_citizen_proxy_author else 0,
        )
        if fixed_colors is None:
            if claimant_id:
                false_claimant_ids.add(claimant_id)
            continue

        candidate_black_teams = _candidate_black_teams(
            fixed_colors,
            player_ids=player_ids,
            alive_states=frozen_alive_states,
        )
        if not candidate_black_teams:
            if claimant_id:
                false_claimant_ids.add(claimant_id)
            continue
        possible_black_teams.extend(candidate_black_teams)

    if possible_black_teams:
        for user_id in player_ids:
            is_black = [user_id in black_team for black_team in possible_black_teams]
            if all(is_black):
                set_known_color(user_id, "black", "версии и состав живых игроков")
            elif not any(is_black):
                set_known_color(user_id, "red", "версии и состав живых игроков")

    for claimant_id in false_claimant_ids:
        set_known_color(claimant_id, "black", "очевидно ложное вскрытие")

    if not possible_black_teams:
        known_color_black_teams = _candidate_black_teams(
            known_colors,
            player_ids=player_ids,
            alive_states=frozen_alive_states,
        )
        for user_id in player_ids:
            is_black = [user_id in black_team for black_team in known_color_black_teams]
            if is_black and all(is_black):
                set_known_color(
                    user_id,
                    "black",
                    "известные цвета и состав живых игроков",
                )
            elif known_color_black_teams and not any(is_black):
                set_known_color(
                    user_id,
                    "red",
                    "известные цвета и состав живых игроков",
                )

    known_black_ids = {user_id for user_id, color in known_colors.items() if color == "black"}
    if len(known_black_ids) == 3:
        for user_id in player_ids:
            set_known_color(
                user_id,
                "black" if user_id in known_black_ids else "red",
                "три известных чёрных образуют чёрную тройку",
            )
    if sources is not None:
        sources.update(known_color_sources)
    return known_colors


def _apply_night_opinion_points(
        points: dict[int, Decimal],
        *,
        roles: Mapping[object, Any],
        actions: Iterable[Mapping[str, Any]],
        apply_rule: Callable[[int, str], dict[str, Any]],
        audit: list[dict[str, Any]] | None = None,
) -> None:
    player_ids = set(points)
    if not player_ids:
        return

    active_versions: list[dict[str, Any]] = []
    sheriff_checks: dict[int, set[int]] = {}
    alive_ids = set(player_ids)
    alive_states: list[frozenset[int]] = [frozenset(alive_ids)]

    def remember_alive_state(next_alive_ids: set[int]) -> None:
        snapshot = frozenset(next_alive_ids)
        if alive_states[-1] != snapshot:
            alive_states.append(snapshot)

    for action_index, action in enumerate(actions, start=1):
        action_order = _action_user_id(action, "_scoring_action_order") or action_index
        action_type = _action_type(action)
        if action_type == "versions":
            active_versions = _normalize_action_versions(action.get("versions"), player_ids)
            continue

        if action_type == "day_start":
            logged_alive_ids = set(_action_user_ids(action, "alive")) & player_ids
            if logged_alive_ids:
                alive_ids = logged_alive_ids
                remember_alive_state(alive_ids)
            continue

        if action_type == "death":
            target_id = _action_user_id(action, "target_id")
            if target_id in alive_ids:
                alive_ids.remove(target_id)
                remember_alive_state(alive_ids)
            continue

        if action_type == "night_check":
            actor_id = _action_user_id(action, "actor_id")
            target_id = _action_user_id(action, "target_id")
            if (
                    actor_id in player_ids
                    and target_id in player_ids
                    and _role_for_user(roles, actor_id) == "sheriff"
            ):
                sheriff_checks.setdefault(actor_id, set()).add(target_id)
            continue

        if action_type != "night_opinions":
            continue

        action_versions = action.get("versions")
        versions = (
            _normalize_action_versions(action_versions, player_ids)
            if isinstance(action_versions, list)
            else active_versions
        )
        action_alive_ids = set(_action_user_ids(action, "alive")) & player_ids
        if action_alive_ids:
            alive_ids = action_alive_ids
            remember_alive_state(alive_ids)
        opinion_alive_ids = alive_ids
        opinion_alive_states = tuple(alive_states)
        if not opinion_alive_states or opinion_alive_states[-1] != frozenset(opinion_alive_ids):
            opinion_alive_states = (*opinion_alive_states, frozenset(opinion_alive_ids))

        raw_opinions = action.get("opinions")
        if not isinstance(raw_opinions, Mapping):
            continue
        for raw_actor_id, raw_picks in raw_opinions.items():
            actor_id = _action_user_id({"actor_id": raw_actor_id}, "actor_id")
            if actor_id not in player_ids or _role_for_user(roles, actor_id) not in RED_ROLES:
                continue
            if not isinstance(raw_picks, Mapping):
                continue

            obvious_color_sources: dict[int, str] = {}
            obvious_colors = _night_opinion_obvious_colors(
                actor_id=actor_id,
                roles=roles,
                player_ids=player_ids,
                active_versions=versions,
                sheriff_checks=sheriff_checks,
                alive_states=opinion_alive_states,
                sources=obvious_color_sources,
            )
            for raw_target_id, raw_guess in raw_picks.items():
                target_id = _action_user_id({"target_id": raw_target_id}, "target_id")
                guess_color = _night_opinion_guess_side(raw_guess)
                actual_color = _team_for_role(_role_for_user(roles, target_id))
                if (
                        target_id not in player_ids
                        or target_id == actor_id
                        or not guess_color
                        or not actual_color
                ):
                    continue

                audit_item = {
                    "action_order": action_order,
                    "type": "night_opinion",
                    "actor_id": actor_id,
                    "target_id": target_id,
                    "guess_color": guess_color,
                    "actual_color": actual_color,
                    "obvious": target_id in obvious_colors,
                    "obvious_color": obvious_colors.get(target_id),
                    "obvious_reason": obvious_color_sources.get(target_id),
                    "reason": "obvious_color" if target_id in obvious_colors else "",
                }
                if target_id in obvious_colors:
                    if audit is not None:
                        audit.append(audit_item)
                    continue

                rule_key = "night_opinion_correct" if guess_color == actual_color else "night_opinion_wrong"
                audit_item["actor_adjustment"] = apply_rule(
                    actor_id,
                    rule_key,
                )
                if audit is not None:
                    audit.append(audit_item)


def _apply_farewell_points(
        points: dict[int, Decimal],
        *,
        roles: Mapping[object, Any],
        actions: Iterable[Mapping[str, Any]],
        apply_rule: Callable[[int, str], dict[str, Any]],
        audit: list[dict[str, Any]] | None = None,
) -> None:
    player_ids = set(points)
    if not player_ids:
        return

    active_versions: list[dict[str, Any]] = []
    sheriff_checks: dict[int, set[int]] = {}
    alive_ids = set(player_ids)
    alive_states: list[frozenset[int]] = [frozenset(alive_ids)]

    def remember_alive_state(next_alive_ids: set[int]) -> None:
        snapshot = frozenset(next_alive_ids)
        if alive_states[-1] != snapshot:
            alive_states.append(snapshot)

    for action_index, action in enumerate(actions, start=1):
        action_order = _action_user_id(action, "_scoring_action_order") or action_index
        action_type = _action_type(action)
        if action_type == "versions":
            active_versions = _normalize_action_versions(action.get("versions"), player_ids)
            continue

        if action_type == "day_start":
            logged_alive_ids = set(_action_user_ids(action, "alive")) & player_ids
            if logged_alive_ids:
                alive_ids = logged_alive_ids
                remember_alive_state(alive_ids)
            continue

        if action_type == "death":
            target_id = _action_user_id(action, "target_id")
            if target_id in alive_ids:
                alive_ids.remove(target_id)
                remember_alive_state(alive_ids)
            continue

        if action_type == "night_check":
            actor_id = _action_user_id(action, "actor_id")
            target_id = _action_user_id(action, "target_id")
            if (
                    actor_id in player_ids
                    and target_id in player_ids
                    and _role_for_user(roles, actor_id) == "sheriff"
            ):
                sheriff_checks.setdefault(actor_id, set()).add(target_id)
            continue

        if action_type != "farewell":
            continue

        raw_wills = action.get("wills")
        if not isinstance(raw_wills, Mapping):
            continue
        actor_id = _action_user_id(action, "actor_id")
        if actor_id not in player_ids:
            continue

        actor_is_red = _role_for_user(roles, actor_id) in RED_ROLES
        raw_contexts = action.get("contexts")
        contexts = raw_contexts if isinstance(raw_contexts, Mapping) else {}
        for raw_target_id, raw_guess in raw_wills.items():
            target_id = _action_user_id({"target_id": raw_target_id}, "target_id")
            guess_color = _night_opinion_guess_side(raw_guess)
            actual_color = _team_for_role(_role_for_user(roles, target_id))
            if (
                    target_id not in player_ids
                    or target_id == actor_id
                    or not guess_color
                    or not actual_color
            ):
                continue

            if not actor_is_red:
                if audit is not None:
                    audit.append(
                        {
                            "action_order": action_order,
                            "type": "farewell",
                            "actor_id": actor_id,
                            "target_id": target_id,
                            "guess_color": guess_color,
                            "actual_color": actual_color,
                            "obvious": False,
                            "obvious_color": None,
                            "reason": "black_author",
                        }
                    )
                continue

            raw_context = contexts.get(str(target_id), contexts.get(target_id))
            context = raw_context if isinstance(raw_context, Mapping) else {}
            raw_versions = context.get("versions") if context else None
            versions = (
                _normalize_action_versions(raw_versions, player_ids)
                if isinstance(raw_versions, list)
                else active_versions
            )
            context_alive_ids = set(_action_user_ids(context, "alive")) & player_ids
            farewell_alive_ids = context_alive_ids or alive_ids
            farewell_alive_states = tuple(alive_states)
            if not farewell_alive_states or farewell_alive_states[-1] != frozenset(farewell_alive_ids):
                farewell_alive_states = (*farewell_alive_states, frozenset(farewell_alive_ids))

            obvious_color_sources: dict[int, str] = {}
            obvious_colors = _night_opinion_obvious_colors(
                actor_id=actor_id,
                roles=roles,
                player_ids=player_ids,
                active_versions=versions,
                sheriff_checks=sheriff_checks,
                alive_states=farewell_alive_states,
                sources=obvious_color_sources,
            )
            audit_item = {
                "action_order": action_order,
                "type": "farewell",
                "actor_id": actor_id,
                "target_id": target_id,
                "guess_color": guess_color,
                "actual_color": actual_color,
                "obvious": target_id in obvious_colors,
                "obvious_color": obvious_colors.get(target_id),
                "obvious_reason": obvious_color_sources.get(target_id),
                "reason": "obvious_color" if target_id in obvious_colors else "",
            }
            if target_id in obvious_colors:
                if audit is not None:
                    audit.append(audit_item)
                continue

            if actual_color == "red":
                rule_key = "farewell_red_correct" if guess_color == "red" else "farewell_red_wrong"
                audit_item["actor_adjustment"] = apply_rule(actor_id, rule_key)
                if audit is not None:
                    audit.append(audit_item)
                continue

            rule_key = "farewell_black_correct" if guess_color == "black" else "farewell_black_wrong"
            audit_item["actor_adjustment"] = apply_rule(actor_id, rule_key)
            if guess_color != "red":
                if audit is not None:
                    audit.append(audit_item)
                continue

            target_is_claimant = any(
                _action_user_id(version, "claimant_id") == target_id
                for version in versions
            )
            black_bonus_rule_key = (
                "farewell_claimant_black_named_red"
                if target_is_claimant
                else "farewell_black_named_red"
            )
            audit_item["target_adjustment"] = apply_rule(target_id, black_bonus_rule_key)
            if audit is not None:
                audit.append(audit_item)


def _black_wins_if_a_red_leaves(
        alive_ids: Iterable[int],
        *,
        roles: Mapping[object, Any],
) -> bool:
    red_alive = 0
    black_alive = 0
    for user_id in alive_ids:
        team = _team_for_role(_role_for_user(roles, user_id))
        if team == "red":
            red_alive += 1
        elif team == "black":
            black_alive += 1
    return black_alive > 0 and black_alive >= max(red_alive - 2, 0)


def _apply_check_and_version_points(
        points: dict[int, Decimal],
        *,
        roles: Mapping[object, Any],
        actions: Iterable[Mapping[str, Any]],
        result: object,
        apply_rule: Callable[[int, str], dict[str, Any]],
        audit: list[dict[str, Any]] | None = None,
) -> None:
    player_ids = set(points)
    if not player_ids:
        return

    active_versions: list[dict[str, Any]] = []
    last_versions_action_order = 0
    citizen_false_check_penalized: set[int] = set()
    sheriff_black_check_streak: dict[int, tuple[int, int]] = {}
    sheriff_black_check_awarded: set[int] = set()
    don_first_two_checks: dict[int, list[int]] = {}
    don_missed_sheriff_penalized: set[int] = set()

    for action_index, action in enumerate(actions, start=1):
        action_order = _action_user_id(action, "_scoring_action_order") or action_index
        action_type = _action_type(action)
        if action_type == "versions":
            active_versions = _normalize_action_versions(action.get("versions"), player_ids)
            last_versions_action_order = action_order
            for version in active_versions:
                actor_id = _action_user_id(version, "claimant_id")
                if (
                        actor_id not in player_ids
                        or actor_id in citizen_false_check_penalized
                        or _role_for_user(roles, actor_id) != "citizen"
                ):
                    continue

                for check in version.get("checks", []):
                    if not isinstance(check, Mapping):
                        continue
                    target_id = _action_user_id(check, "target_id")
                    guess_color = str(check.get("verdict") or "").strip().lower()
                    actual_color = _team_for_role(_role_for_user(roles, target_id))
                    if target_id not in player_ids or guess_color == actual_color:
                        continue
                    citizen_false_check_penalized.add(actor_id)
                    audit_item = {
                        "action_order": action_order,
                        "type": "check_scoring",
                        "check_kind": "citizen_false_check",
                        "actor_id": actor_id,
                        "target_id": target_id,
                        "guess_color": guess_color,
                        "actual_color": actual_color,
                        "actor_adjustment": apply_rule(actor_id, "citizen_false_check")
                    }
                    if audit is not None:
                        audit.append(audit_item)
                    break
            continue

        if action_type != "night_check":
            continue

        actor_id = _action_user_id(action, "actor_id")
        target_id = _action_user_id(action, "target_id")
        if actor_id not in player_ids or target_id not in player_ids:
            continue
        actor_role = _role_for_user(roles, actor_id)

        if actor_role == "sheriff":
            claimant_ids = {
                _action_user_id(version, "claimant_id")
                for version in active_versions
            }
            target_is_unobvious_black = (
                    _is_black(_role_for_user(roles, target_id))
                    and target_id not in claimant_ids
            )
            if not target_is_unobvious_black:
                sheriff_black_check_streak[actor_id] = (0, 0)
                continue

            previous_count, previous_target_id = sheriff_black_check_streak.get(actor_id, (0, 0))
            current_count = previous_count + 1
            sheriff_black_check_streak[actor_id] = (current_count, target_id)
            if current_count < 2 or actor_id in sheriff_black_check_awarded:
                continue

            sheriff_black_check_awarded.add(actor_id)
            audit_item = {
                "action_order": action_order,
                "type": "check_scoring",
                "check_kind": "sheriff_two_unobvious_black_checks",
                "actor_id": actor_id,
                "target_id": target_id,
                "previous_target_id": previous_target_id,
                "actor_adjustment": apply_rule(actor_id, "sheriff_two_unobvious_black_checks")
            }
            if audit is not None:
                audit.append(audit_item)
            continue

        if actor_role != "don" or actor_id in don_missed_sheriff_penalized:
            continue

        checked_ids = don_first_two_checks.setdefault(actor_id, [])
        if len(checked_ids) >= 2:
            continue
        checked_ids.append(target_id)
        if len(checked_ids) < 2 or any(
                _role_for_user(roles, checked_id) == "sheriff"
                for checked_id in checked_ids
        ):
            continue

        don_missed_sheriff_penalized.add(actor_id)
        audit_item = {
            "action_order": action_order,
            "type": "check_scoring",
            "check_kind": "don_missed_sheriff_two_checks",
            "actor_id": actor_id, "target_id": target_id,
            "previous_target_id": checked_ids[0],
            "actor_adjustment": apply_rule(actor_id, "don_missed_sheriff_two_checks")
        }
        if audit is not None:
            audit.append(audit_item)

    if str(result or "").strip().lower() != "black" or not active_versions:
        return

    for version in active_versions:
        actor_id = _action_user_id(version, "claimant_id")
        if actor_id not in player_ids or _role_for_user(roles, actor_id) != "sheriff":
            continue
        for check in version.get("checks", []):
            if not isinstance(check, Mapping):
                continue
            target_id = _action_user_id(check, "target_id")
            guess_color = str(check.get("verdict") or "").strip().lower()
            actual_color = _team_for_role(_role_for_user(roles, target_id))
            if target_id not in player_ids or guess_color == actual_color:
                continue
            audit_item = {
                "action_order": last_versions_action_order,
                "type": "check_scoring",
                "check_kind": "sheriff_false_check_black_win",
                "actor_id": actor_id,
                "target_id": target_id,
                "guess_color": guess_color,
                "actual_color": actual_color,
                "actor_adjustment": apply_rule(actor_id, "sheriff_false_check_black_win")
            }
            if audit is not None:
                audit.append(audit_item)
            break


def _apply_critical_nomination_points(
        points: dict[int, Decimal],
        *,
        roles: Mapping[object, Any],
        actions: Iterable[Mapping[str, Any]],
        apply_rule: Callable[[int, str], dict[str, Any]],
        audit: list[dict[str, Any]] | None = None,
) -> None:
    player_ids = set(points)
    if not player_ids:
        return

    active_versions: list[dict[str, Any]] = []
    sheriff_checks: dict[int, set[int]] = {}
    alive_ids = set(player_ids)
    alive_states: list[frozenset[int]] = [frozenset(alive_ids)]
    nominations: dict[tuple[int, int], dict[str, Any]] = {}
    first_votes: dict[int, dict[str, Any]] = {}
    departed_black_ids_by_day: dict[int, set[int]] = {}
    black_win_days: set[int] = set()

    def remember_alive_state(next_alive_ids: set[int]) -> None:
        snapshot = frozenset(next_alive_ids)
        if alive_states[-1] != snapshot:
            alive_states.append(snapshot)

    for action_index, action in enumerate(actions, start=1):
        action_order = _action_user_id(action, "_scoring_action_order") or action_index
        action_type = _action_type(action)
        if action_type == "versions":
            active_versions = _normalize_action_versions(action.get("versions"), player_ids)
            continue

        if action_type == "day_start":
            logged_alive_ids = set(_action_user_ids(action, "alive")) & player_ids
            if logged_alive_ids:
                alive_ids = logged_alive_ids
                remember_alive_state(alive_ids)
            continue

        if action_type == "night_check":
            actor_id = _action_user_id(action, "actor_id")
            target_id = _action_user_id(action, "target_id")
            if (
                    actor_id in player_ids
                    and target_id in player_ids
                    and _role_for_user(roles, actor_id) == "sheriff"
            ):
                sheriff_checks.setdefault(actor_id, set()).add(target_id)
            continue

        if action_type == "nominate":
            day = _action_user_id(action, "day")
            actor_id = _action_user_id(action, "actor_id")
            target_id = _action_user_id(action, "target_id")
            if day <= 0 or actor_id not in player_ids or target_id not in player_ids:
                continue

            raw_context = action.get("scoring_context")
            context = raw_context if isinstance(raw_context, Mapping) else {}
            raw_versions = context.get("versions")
            versions = (
                _normalize_action_versions(raw_versions, player_ids)
                if isinstance(raw_versions, list)
                else active_versions
            )
            context_alive_ids = set(_action_user_ids(context, "alive")) & player_ids
            nomination_alive_ids = context_alive_ids or set(alive_ids)
            nomination_alive_states = tuple(alive_states)
            if (
                    not nomination_alive_states
                    or nomination_alive_states[-1] != frozenset(nomination_alive_ids)
            ):
                nomination_alive_states = (*nomination_alive_states, frozenset(nomination_alive_ids))

            raw_speakers_after = context.get("speakers_after")
            nominations.setdefault(
                (day, target_id),
                {
                    "action_order": action_order,
                    "actor_id": actor_id,
                    "target_id": target_id,
                    "versions": versions,
                    "alive_states": nomination_alive_states,
                    "speakers_after": (
                        set(_action_user_ids({"speakers_after": raw_speakers_after}, "speakers_after"))
                        if isinstance(raw_speakers_after, list)
                        else None
                    ),
                },
            )
            continue

        if action_type == "vote":
            day = _action_user_id(action, "day")
            if day <= 0 or day in first_votes:
                continue
            candidates = [
                target_id
                for target_id in _action_user_ids(action, "targets")
                if target_id in player_ids
            ]
            if not candidates:
                continue
            logged_alive_ids = set(_action_user_ids(action, "alive")) & player_ids
            first_votes[day] = {
                "candidates": candidates,
                "alive": logged_alive_ids or set(alive_ids),
            }
            continue

        if action_type != "death":
            continue

        target_id = _action_user_id(action, "target_id")
        day = _action_user_id(action, "day")
        reason = str(action.get("reason") or "").strip().lower()
        if reason == "vote" and target_id in player_ids and day > 0:
            if _is_black(_role_for_user(roles, target_id)):
                departed_black_ids_by_day.setdefault(day, set()).add(target_id)
            if str(action.get("result_after") or "").strip().lower() == "black":
                black_win_days.add(day)

        if target_id in alive_ids:
            alive_ids.remove(target_id)
            remember_alive_state(alive_ids)

    for day, first_vote in first_votes.items():
        candidates = first_vote["candidates"]
        black_candidates = [
            user_id
            for user_id in candidates
            if _is_black(_role_for_user(roles, user_id))
        ]
        if len(black_candidates) != 1:
            continue

        target_id = black_candidates[0]
        if target_id not in departed_black_ids_by_day.get(day, set()):
            continue

        nomination = nominations.get((day, target_id))
        if nomination is None:
            continue

        actor_id = nomination["actor_id"]
        actor_team = _team_for_role(_role_for_user(roles, actor_id))
        if actor_team not in {"red", "black"}:
            continue

        audit_item = {
            "action_order": nomination["action_order"],
            "type": "critical_nomination",
            "actor_id": actor_id,
            "target_id": target_id,
            "actor_team": actor_team,
            "candidate_ids": candidates,
            "obvious": False,
            "reason": "",
        }
        if day in black_win_days:
            audit_item["reason"] = "black_win_after_vote"
            if audit is not None:
                audit.append(audit_item)
            continue

        speakers_after = nomination["speakers_after"]
        if speakers_after is None:
            audit_item["reason"] = "speech_order_unknown"
            if audit is not None:
                audit.append(audit_item)
            continue
        if any(
                _team_for_role(_role_for_user(roles, speaker_id)) == "red"
                for speaker_id in speakers_after
        ):
            audit_item["reason"] = "red_speech_after"
            if audit is not None:
                audit.append(audit_item)
            continue

        if not _black_wins_if_a_red_leaves(first_vote["alive"], roles=roles):
            audit_item["reason"] = "not_critical"
            if audit is not None:
                audit.append(audit_item)
            continue

        if actor_team == "black":
            audit_item["actor_adjustment"] = apply_rule(
                actor_id,
                "nomination_black_prevents_black_win",
            )
            if audit is not None:
                audit.append(audit_item)
            continue

        obvious_color_sources: dict[int, str] = {}
        obvious_colors = _night_opinion_obvious_colors(
            actor_id=actor_id,
            roles=roles,
            player_ids=player_ids,
            active_versions=nomination["versions"],
            sheriff_checks=sheriff_checks,
            alive_states=nomination["alive_states"],
            sources=obvious_color_sources,
        )
        audit_item["obvious"] = target_id in obvious_colors
        audit_item["obvious_color"] = obvious_colors.get(target_id)
        audit_item["obvious_reason"] = obvious_color_sources.get(target_id)
        if target_id in obvious_colors:
            audit_item["reason"] = "obvious_color"
            if audit is not None:
                audit.append(audit_item)
            continue

        audit_item["actor_adjustment"] = apply_rule(
            actor_id,
            "nomination_red_last_hope",
        )
        if audit is not None:
            audit.append(audit_item)


def _apply_action_points(
        points: dict[int, Decimal],
        *,
        roles: Mapping[object, Any],
        actions: Iterable[Mapping[str, Any]],
        rules: Mapping[str, object],
        result: object = "",
        breakdown: dict[int, list[dict[str, Any]]] | None = None,
        audit: list[dict[str, Any]] | None = None,
) -> None:
    rule_values: dict[str, Decimal] = {}
    for key, default in GAME_SCORING_RULE_DEFAULTS.items():
        parsed = _as_decimal(rules.get(key))
        rule_values[key] = default if parsed is None else parsed

    def apply_rule(user_id: int, rule_key: str, **placeholders: object) -> dict[str, Any]:
        value = rule_values[rule_key]
        label = _scoring_rule_label(rules, rule_key, **placeholders)
        points[user_id] += value
        _record_scoring_adjustment(
            breakdown,
            user_id=user_id,
            rule_key=rule_key,
            label=label,
            value=value,
        )
        return {
            "rule_key": rule_key,
            "label": label,
            "points": normalize_game_points_value(value),
        }

    normalized_actions = [
        {**action, "_scoring_action_order": action_order}
        for action_order, action in enumerate(actions, start=1)
        if isinstance(action, Mapping)
    ]

    _apply_night_opinion_points(
        points,
        roles=roles,
        actions=normalized_actions,
        apply_rule=apply_rule,
        audit=audit,
    )
    _apply_farewell_points(
        points,
        roles=roles,
        actions=normalized_actions,
        apply_rule=apply_rule,
        audit=audit,
    )
    _apply_check_and_version_points(
        points,
        roles=roles,
        actions=normalized_actions,
        result=result,
        apply_rule=apply_rule,
        audit=audit,
    )
    _apply_critical_nomination_points(
        points,
        roles=roles,
        actions=normalized_actions,
        apply_rule=apply_rule,
        audit=audit,
    )

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
                        apply_rule(
                            shooter_id,
                            "night_shoot_miss_terminal",
                        )
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
            apply_rule(
                missers[0],
                rule_key,
            )
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
                apply_rule(
                    voter_id,
                    rule_key,
                )
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
                        apply_rule(voter_id, "vote_opponent_team")
            continue

        if action_type == "day_start":
            alive_ids = _action_user_ids(action, "alive")
            if len(alive_ids) >= 7:
                continue
            for user_id in alive_ids:
                if user_id in points and _is_black(_role_for_user(roles, user_id)):
                    apply_rule(user_id, "black_day_under_seven")
            continue

        if action_type == "foul":
            target_id = _action_user_id(action, "target_id")
            try:
                count = int(action.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if target_id in points and count == 4:
                rule_key = "fourth_foul_lost" if foul_loss_after.get(target_id, False) else "fourth_foul"
                apply_rule(
                    target_id,
                    rule_key,
                )
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
            apply_rule(
                target_id,
                rule_key,
                count=count,
            )
            continue

        if action_type == "death":
            target_id = _action_user_id(action, "target_id")
            reason = str(action.get("reason") or "").strip().lower()
            if target_id in points and reason == "suicide":
                rule_key = "suicide_lost" if _action_bool(action, "game_lost_after") else "suicide"
                apply_rule(
                    target_id,
                    rule_key,
                )

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
                            apply_rule(
                                voter_id,
                                penalty_key,
                            )
                    if is_black_win_3v3:
                        for user_id in points:
                            if _is_black(_role_for_user(roles, user_id)):
                                apply_rule(user_id, "black_win_3v3")
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
        apply_rule(
            actor_id,
            f"best_move_black_{black_count}",
        )


def _additional_points_bounds(rules: Mapping[str, object]) -> tuple[Decimal, Decimal]:
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
        _apply_action_points(
            additional_points,
            roles=roles,
            actions=actions,
            rules=active_rules,
            result=normalized_result,
        )
        additional_min, additional_max = _additional_points_bounds(active_rules)
        for user_id, value in additional_points.items():
            base_points[user_id] += min(max(value, additional_min), additional_max)

    return {str(user_id): normalize_game_points_value(value) for user_id, value in base_points.items()}


def calculate_game_scoring_audit(
        *,
        mode: object,
        result: object = "",
        roles: Mapping[object, Any],
        player_ids: Iterable[int | str],
        actions: Iterable[Mapping[str, Any]] | None = None,
        scoring_rules: Mapping[object, Any] | None = None,
) -> list[dict[str, Any]]:
    if normalize_game_mode(mode) != RATING_MODE:
        return []

    active_rules = parse_game_scoring_rules_snapshot(scoring_rules)
    if active_rules is None or actions is None:
        return []

    players = _normalize_user_ids(player_ids)
    audit: list[dict[str, Any]] = []
    _apply_action_points(
        {user_id: Decimal("0") for user_id in players},
        roles=roles,
        actions=actions,
        rules=active_rules,
        result=result,
        audit=audit,
    )
    return audit


def calculate_game_points_breakdown(
        *,
        mode: object,
        result: object,
        roles: Mapping[object, Any],
        player_ids: Iterable[int | str],
        actions: Iterable[Mapping[str, Any]] | None = None,
        scoring_rules: Mapping[object, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    if normalize_game_mode(mode) != RATING_MODE:
        return {}

    players = _normalize_user_ids(player_ids)
    normalized_result = str(result or "").strip().lower()
    base_points = {user_id: Decimal("0") for user_id in players}
    base_reasons = {user_id: "draw" if normalized_result == "draw" else "loss" for user_id in players}
    if normalized_result in DECISIVE_RESULTS:
        for user_id in players:
            if _wins(_role_for_user(roles, user_id), normalized_result):
                base_points[user_id] = Decimal("1")
                base_reasons[user_id] = "win"

    active_rules = parse_game_scoring_rules_snapshot(scoring_rules)
    rules_available = active_rules is not None and actions is not None
    additional_points = {user_id: Decimal("0") for user_id in players}
    adjustments: dict[int, list[dict[str, Any]]] = {}
    additional_min: Decimal | None = None
    additional_max: Decimal | None = None
    if rules_available and active_rules is not None and actions is not None:
        _apply_action_points(
            additional_points,
            roles=roles,
            actions=actions,
            rules=active_rules,
            result=normalized_result,
            breakdown=adjustments,
        )
        additional_min, additional_max = _additional_points_bounds(active_rules)

    result_by_user: dict[str, dict[str, Any]] = {}
    for user_id in players:
        raw_additional = additional_points[user_id]
        applied_additional = raw_additional
        if additional_min is not None and additional_max is not None:
            applied_additional = min(max(raw_additional, additional_min), additional_max)

        result_by_user[str(user_id)] = {
            "base_points": normalize_game_points_value(base_points[user_id]),
            "base_reason": base_reasons[user_id],
            "adjustments": adjustments.get(user_id, []),
            "additional_points_raw": normalize_game_points_value(raw_additional),
            "additional_points": normalize_game_points_value(applied_additional),
            "additional_points_min": normalize_game_points_value(
                additional_min) if additional_min is not None else None,
            "additional_points_max": normalize_game_points_value(
                additional_max) if additional_max is not None else None,
            "additional_points_capped": raw_additional != applied_additional,
            "rules_available": rules_available,
            "final_points": normalize_game_points_value(base_points[user_id] + applied_additional),
        }

    return result_by_user
