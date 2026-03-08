from __future__ import annotations
from typing import Any
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.game import Game

DECISIVE_RESULTS = {"red", "black"}
BLACK_ROLES = {"mafia", "don"}
RED_ROLES = {"citizen", "sheriff"}
FOUL_OR_SUICIDE_REASONS = {"foul", "suicide"}

GAME_STATS_FIELDS: tuple[str, ...] = (
    "games_total_finished",
    "games_decisive",
    "games_won",
    "games_hosted",
    "don_checks_first_night",
    "don_checks_first_night_found",
    "vote_leave_day12",
    "foul_removed_count",
    "vote_for_red_on_black_win_count",
    "farewell_total",
    "farewell_correct",
    "first_killed_best_move_total",
    "best_move_black_0",
    "best_move_black_1",
    "best_move_black_2",
    "best_move_black_3",
    "current_win_streak",
    "current_loss_streak",
    "best_win_streak",
    "best_loss_streak",
    "citizen_games",
    "citizen_wins",
    "sheriff_games",
    "sheriff_wins",
    "mafia_games",
    "mafia_wins",
    "don_games",
    "don_wins",
)


def _safe_int(raw: Any) -> int:
    if raw is None:
        return 0

    if isinstance(raw, bytes):
        try:
            raw = raw.decode()
        except Exception:
            return 0

    try:
        return int(raw)

    except Exception:
        return 0


def _safe_str(raw: Any) -> str:
    if raw is None:
        return ""

    if isinstance(raw, bytes):
        try:
            raw = raw.decode()
        except Exception:
            return ""

    try:
        return str(raw)

    except Exception:
        return ""


def _is_black(role: str) -> bool:
    return role in BLACK_ROLES


def _did_win(role: str, result: str) -> bool:
    if result == "red":
        return role in RED_ROLES

    if result == "black":
        return role in BLACK_ROLES

    return False


def empty_game_stats_row() -> dict[str, int]:
    return {field: 0 for field in GAME_STATS_FIELDS}


def _normalize_roles(raw: Any) -> dict[int, str]:
    out: dict[int, str] = {}
    if not isinstance(raw, dict):
        return out

    for k, v in raw.items():
        uid = _safe_int(k)
        if uid <= 0:
            continue
        role = _safe_str(v).strip()
        if not role:
            continue
        out[uid] = role
    return out


def _normalize_actions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
    return out


def _inc(d: dict[int, int], key: int, delta: int = 1) -> None:
    if key <= 0 or delta == 0:
        return

    d[key] = d.get(key, 0) + delta


def _parse_actions(actions: list[dict[str, Any]], roles: dict[int, str]) -> dict[str, Any]:
    don_checks_first_night: dict[int, int] = {}
    don_checks_first_night_found: dict[int, int] = {}
    foul_removed_count: dict[int, int] = {}
    vote_for_red_on_black_win_count: dict[int, int] = {}
    leave_vote_day12: dict[int, int] = {}
    farewell_total: dict[int, int] = {}
    farewell_correct: dict[int, int] = {}
    first_killed_best_move_total: dict[int, int] = {}
    best_move_bucket: dict[int, dict[int, int]] = {}
    last_vote_targets: dict[int, int] = {}
    last_vote_day_number = 0
    final_vote_red_voters_on_red_target: set[int] = set()
    foul_or_suicide_death_seen: set[int] = set()
    don_checked_first_night_seen: set[int] = set()
    don_checked_first_night_found_seen: set[int] = set()

    for action in actions:
        action_type = _safe_str(action.get("type"))

        if action_type == "night_check":
            actor_id = _safe_int(action.get("actor_id"))
            checker_role = _safe_str(action.get("checker_role"))
            day_number = _safe_int(action.get("day"))
            if actor_id > 0 and checker_role == "don" and day_number == 1:
                if actor_id not in don_checked_first_night_seen:
                    _inc(don_checks_first_night, actor_id, 1)
                    don_checked_first_night_seen.add(actor_id)
                if _safe_str(action.get("target_role")) == "sheriff":
                    if actor_id not in don_checked_first_night_found_seen:
                        _inc(don_checks_first_night_found, actor_id, 1)
                        don_checked_first_night_found_seen.add(actor_id)
            continue

        if action_type == "death":
            target_id = _safe_int(action.get("target_id"))
            day_number = _safe_int(action.get("day"))
            reason = _safe_str(action.get("reason"))
            if reason == "vote" and day_number in (1, 2):
                _inc(leave_vote_day12, target_id, 1)
            if reason == "vote":
                red_voters: set[int] = set()
                if target_id > 0 and last_vote_targets:
                    same_day = 0 < day_number == last_vote_day_number > 0
                    if same_day or day_number <= 0 or last_vote_day_number <= 0:
                        target_role = roles.get(target_id, "")
                        if target_role in RED_ROLES:
                            for voter_id, voted_target in last_vote_targets.items():
                                if voted_target != target_id:
                                    continue
                                voter_role = roles.get(voter_id, "")
                                if voter_role in RED_ROLES:
                                    red_voters.add(voter_id)
                final_vote_red_voters_on_red_target = red_voters
            if reason in FOUL_OR_SUICIDE_REASONS and target_id > 0 and target_id not in foul_or_suicide_death_seen:
                _inc(foul_removed_count, target_id, 1)
                foul_or_suicide_death_seen.add(target_id)
            continue

        if action_type == "vote":
            votes_raw = action.get("votes")
            if not isinstance(votes_raw, dict):
                continue
            parsed_votes: dict[int, int] = {}
            for target_raw, voters_raw in votes_raw.items():
                target_id = _safe_int(target_raw)
                if target_id <= 0 or not isinstance(voters_raw, list):
                    continue
                for voter_raw in voters_raw:
                    voter_id = _safe_int(voter_raw)
                    if voter_id > 0:
                        parsed_votes[voter_id] = target_id
            if parsed_votes:
                last_vote_targets = parsed_votes
                last_vote_day_number = _safe_int(action.get("day"))
            continue

        if action_type == "farewell":
            actor_id = _safe_int(action.get("actor_id"))
            wills = action.get("wills")
            if actor_id <= 0 or not isinstance(wills, dict):
                continue
            actor_role = roles.get(actor_id, "")
            if _is_black(actor_role):
                continue
            for target_raw, verdict_raw in wills.items():
                target_id = _safe_int(target_raw)
                if target_id <= 0:
                    continue
                verdict = _safe_str(verdict_raw)
                if verdict not in ("citizen", "mafia"):
                    continue
                target_role = roles.get(target_id, "")
                if not target_role:
                    continue
                expected = "mafia" if _is_black(target_role) else "citizen"
                _inc(farewell_total, actor_id, 1)
                if verdict == expected:
                    _inc(farewell_correct, actor_id, 1)
            continue

        if action_type == "best_move":
            actor_id = _safe_int(action.get("actor_id"))
            if actor_id <= 0:
                continue
            _inc(first_killed_best_move_total, actor_id, 1)
            bucket = best_move_bucket.setdefault(actor_id, {0: 0, 1: 0, 2: 0, 3: 0})
            targets_raw = action.get("targets")
            if not isinstance(targets_raw, list):
                bucket[0] = bucket.get(0, 0) + 1
                continue
            targets: list[int] = []
            for target_raw in targets_raw:
                target_id = _safe_int(target_raw)
                if target_id <= 0 or target_id in targets:
                    continue
                targets.append(target_id)
                if len(targets) >= 3:
                    break
            if len(targets) == 0:
                bucket[0] = bucket.get(0, 0) + 1
                continue
            black_hits = 0
            for target_id in targets:
                if _is_black(roles.get(target_id, "")):
                    black_hits += 1
            black_hits = max(0, min(3, black_hits))
            bucket[black_hits] = bucket.get(black_hits, 0) + 1
            continue

    for voter_id in final_vote_red_voters_on_red_target:
        vote_for_red_on_black_win_count[voter_id] = 1

    return {
        "don_checks_first_night": don_checks_first_night,
        "don_checks_first_night_found": don_checks_first_night_found,
        "foul_removed_count": foul_removed_count,
        "vote_for_red_on_black_win_count": vote_for_red_on_black_win_count,
        "leave_vote_day12": leave_vote_day12,
        "farewell_total": farewell_total,
        "farewell_correct": farewell_correct,
        "first_killed_best_move_total": first_killed_best_move_total,
        "best_move_bucket": best_move_bucket,
    }


def _apply_game_to_row(row: dict[str, int], *, uid: int, roles: dict[int, str], players: set[int], head_id: int, result: str, parsed: dict[str, Any]) -> None:
    if uid <= 0 or result not in DECISIVE_RESULTS:
        return

    in_players = uid in players
    role = roles.get(uid, "")

    if in_players:
        row["games_total_finished"] += 1
        row["games_decisive"] += 1
        won = _did_win(role, result)
        if won:
            row["games_won"] += 1
            row["current_win_streak"] += 1
            row["current_loss_streak"] = 0
            if row["current_win_streak"] > row["best_win_streak"]:
                row["best_win_streak"] = row["current_win_streak"]
        else:
            row["current_loss_streak"] += 1
            row["current_win_streak"] = 0
            if row["current_loss_streak"] > row["best_loss_streak"]:
                row["best_loss_streak"] = row["current_loss_streak"]

        if role == "citizen":
            row["citizen_games"] += 1
            if won:
                row["citizen_wins"] += 1
        elif role == "sheriff":
            row["sheriff_games"] += 1
            if won:
                row["sheriff_wins"] += 1
        elif role == "mafia":
            row["mafia_games"] += 1
            if won:
                row["mafia_wins"] += 1
        elif role == "don":
            row["don_games"] += 1
            if won:
                row["don_wins"] += 1

        row["don_checks_first_night"] += _safe_int(parsed["don_checks_first_night"].get(uid))
        row["don_checks_first_night_found"] += _safe_int(parsed["don_checks_first_night_found"].get(uid))
        row["vote_leave_day12"] += _safe_int(parsed["leave_vote_day12"].get(uid))
        row["foul_removed_count"] += _safe_int(parsed["foul_removed_count"].get(uid))
        if result == "black":
            row["vote_for_red_on_black_win_count"] += _safe_int(parsed["vote_for_red_on_black_win_count"].get(uid))
        row["farewell_total"] += _safe_int(parsed["farewell_total"].get(uid))
        row["farewell_correct"] += _safe_int(parsed["farewell_correct"].get(uid))
        row["first_killed_best_move_total"] += _safe_int(parsed["first_killed_best_move_total"].get(uid))

        best_move_bucket: dict[int, int] = parsed["best_move_bucket"].get(uid) or {}
        row["best_move_black_0"] += _safe_int(best_move_bucket.get(0))
        row["best_move_black_1"] += _safe_int(best_move_bucket.get(1))
        row["best_move_black_2"] += _safe_int(best_move_bucket.get(2))
        row["best_move_black_3"] += _safe_int(best_move_bucket.get(3))

    if 0 < head_id == uid:
        row["games_hosted"] += 1


def _build_game_payload(game: Game) -> dict[str, Any] | None:
    result = _safe_str(getattr(game, "result", ""))
    if result not in DECISIVE_RESULTS:
        return None

    roles = _normalize_roles(getattr(game, "roles", {}))
    players = set(roles.keys())
    head_id = _safe_int(getattr(game, "head_id", 0))
    actions = _normalize_actions(getattr(game, "actions", []))
    parsed = _parse_actions(actions, roles)

    return {
        "result": result,
        "roles": roles,
        "players": players,
        "head_id": head_id,
        "parsed": parsed,
    }


async def build_user_game_stats_row(session: AsyncSession, user_id: int, *, game_id_min: int | None = None, game_id_max: int | None = None) -> dict[str, int]:
    uid = _safe_int(user_id)
    if uid <= 0:
        raise ValueError("invalid_user_id")

    filters = [or_(Game.head_id == uid, Game.roles.has_key(str(uid)))]
    min_id = _safe_int(game_id_min) if game_id_min is not None else 0
    max_id = _safe_int(game_id_max) if game_id_max is not None else 0
    if min_id > 0:
        filters.append(Game.id >= min_id)
    if max_id > 0:
        filters.append(Game.id <= max_id)

    row = empty_game_stats_row()
    game_rows = await session.execute(select(Game).where(*filters).order_by(Game.finished_at.asc(), Game.id.asc()))
    for game in game_rows.scalars().all():
        payload = _build_game_payload(game)
        if not payload:
            continue
        _apply_game_to_row(
            row,
            uid=uid,
            roles=payload["roles"],
            players=payload["players"],
            head_id=payload["head_id"],
            result=payload["result"],
            parsed=payload["parsed"],
        )
    return row
