from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.game import Game
from ..models.stats import UserGameStats

DECISIVE_RESULTS = {"red", "black"}
FINISHED_RESULTS = {"red", "black", "draw"}
BLACK_ROLES = {"mafia", "don"}
RED_ROLES = {"citizen", "sheriff"}


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
    fouls_received: dict[int, int] = {}
    don_checks_first_night: dict[int, int] = {}
    don_checks_first_night_found: dict[int, int] = {}
    misses_due_to_me: dict[int, int] = {}
    leave_vote_day12: dict[int, int] = {}
    farewell_total: dict[int, int] = {}
    farewell_correct: dict[int, int] = {}
    first_killed_best_move_total: dict[int, int] = {}
    best_move_bucket: dict[int, dict[int, int]] = {}

    for action in actions:
        action_type = _safe_str(action.get("type"))

        if action_type == "foul":
            _inc(fouls_received, _safe_int(action.get("target_id")), 1)
            continue

        if action_type == "night_check":
            actor_id = _safe_int(action.get("actor_id"))
            checker_role = _safe_str(action.get("checker_role"))
            day_number = _safe_int(action.get("day"))
            if actor_id > 0 and checker_role == "don" and day_number == 1:
                _inc(don_checks_first_night, actor_id, 1)
                if _safe_str(action.get("target_role")) == "sheriff":
                    _inc(don_checks_first_night_found, actor_id, 1)
            continue

        if action_type == "night_shoot_result":
            shooters_raw = action.get("shooters")
            shots_raw = action.get("shots")
            if not isinstance(shooters_raw, list) or not isinstance(shots_raw, dict):
                continue
            shooters = [_safe_int(item) for item in shooters_raw]
            shooters = [uid for uid in shooters if uid > 0]
            if len(shooters) != 3:
                continue
            shots: dict[int, int] = {}
            for k, v in shots_raw.items():
                shooter = _safe_int(k)
                target = _safe_int(v)
                if shooter > 0:
                    shots[shooter] = target
            targets = [shots.get(shooter, 0) for shooter in shooters]
            if any(target <= 0 for target in targets):
                continue
            counts = Counter(targets)
            if sorted(counts.values()) != [1, 2]:
                continue
            odd_target = 0
            for target, cnt in counts.items():
                if cnt == 1:
                    odd_target = target
                    break
            if odd_target <= 0:
                continue
            odd_shooter = 0
            for shooter in shooters:
                if shots.get(shooter) == odd_target:
                    odd_shooter = shooter
                    break
            if odd_shooter > 0:
                _inc(misses_due_to_me, odd_shooter, 1)
            continue

        if action_type == "death":
            target_id = _safe_int(action.get("target_id"))
            day_number = _safe_int(action.get("day"))
            reason = _safe_str(action.get("reason"))
            if reason == "vote" and day_number in (1, 2):
                _inc(leave_vote_day12, target_id, 1)
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
            actor_role = roles.get(actor_id, "")
            if _is_black(actor_role):
                continue
            targets_raw = action.get("targets")
            if not isinstance(targets_raw, list):
                targets_raw = []
            targets: list[int] = []
            for target_raw in targets_raw:
                target_id = _safe_int(target_raw)
                if target_id <= 0 or target_id in targets:
                    continue
                targets.append(target_id)
                if len(targets) >= 3:
                    break
            black_hits = 0
            for target_id in targets:
                if _is_black(roles.get(target_id, "")):
                    black_hits += 1
            if black_hits < 0:
                black_hits = 0
            if black_hits > 3:
                black_hits = 3
            _inc(first_killed_best_move_total, actor_id, 1)
            bucket = best_move_bucket.setdefault(actor_id, {0: 0, 1: 0, 2: 0, 3: 0})
            bucket[black_hits] = bucket.get(black_hits, 0) + 1
            continue

    return {
        "fouls_received": fouls_received,
        "don_checks_first_night": don_checks_first_night,
        "don_checks_first_night_found": don_checks_first_night_found,
        "misses_due_to_me": misses_due_to_me,
        "leave_vote_day12": leave_vote_day12,
        "farewell_total": farewell_total,
        "farewell_correct": farewell_correct,
        "first_killed_best_move_total": first_killed_best_move_total,
        "best_move_bucket": best_move_bucket,
    }


def _to_utc_iso(raw: Any) -> str:
    if isinstance(raw, datetime):
        dt = raw
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _normalize_recent(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        game_id = _safe_int(item.get("game_id"))
        role = _safe_str(item.get("role"))
        result = _safe_str(item.get("result"))
        won = bool(item.get("won"))
        finished_at = _safe_str(item.get("finished_at"))
        if game_id <= 0 or not role or result not in FINISHED_RESULTS:
            continue
        out.append(
            {
                "game_id": game_id,
                "role": role,
                "result": result,
                "won": won,
                "finished_at": finished_at or _to_utc_iso(None),
            }
        )
    return out


def _apply_game_to_user_row(row: UserGameStats, *, uid: int, roles: dict[int, str], players: set[int], head_id: int, result: str, duration_seconds: int, finished_at: Any, game_id: int, parsed: dict[str, Any]) -> None:
    if uid <= 0 or result not in FINISHED_RESULTS:
        return

    in_players = uid in players
    decisive = result in DECISIVE_RESULTS
    role = roles.get(uid, "")

    if in_players:
        row.games_total_finished = _safe_int(row.games_total_finished) + 1
        if result == "draw":
            row.games_draw = _safe_int(row.games_draw) + 1

        if decisive:
            row.games_decisive = _safe_int(row.games_decisive) + 1
            won = _did_win(role, result)
            if won:
                row.games_won = _safe_int(row.games_won) + 1
                row.current_win_streak = _safe_int(row.current_win_streak) + 1
                row.current_loss_streak = 0
                if _safe_int(row.current_win_streak) > _safe_int(row.best_win_streak):
                    row.best_win_streak = _safe_int(row.current_win_streak)
            else:
                row.current_loss_streak = _safe_int(row.current_loss_streak) + 1
                row.current_win_streak = 0
                if _safe_int(row.current_loss_streak) > _safe_int(row.best_loss_streak):
                    row.best_loss_streak = _safe_int(row.current_loss_streak)

            row.total_duration_seconds = _safe_int(row.total_duration_seconds) + max(0, duration_seconds)

            if role == "citizen":
                row.citizen_games = _safe_int(row.citizen_games) + 1
                if won:
                    row.citizen_wins = _safe_int(row.citizen_wins) + 1
            elif role == "sheriff":
                row.sheriff_games = _safe_int(row.sheriff_games) + 1
                if won:
                    row.sheriff_wins = _safe_int(row.sheriff_wins) + 1
            elif role == "mafia":
                row.mafia_games = _safe_int(row.mafia_games) + 1
                if won:
                    row.mafia_wins = _safe_int(row.mafia_wins) + 1
            elif role == "don":
                row.don_games = _safe_int(row.don_games) + 1
                if won:
                    row.don_wins = _safe_int(row.don_wins) + 1

            row.total_fouls_received = _safe_int(row.total_fouls_received) + _safe_int(parsed["fouls_received"].get(uid))
            row.don_checks_first_night = _safe_int(row.don_checks_first_night) + _safe_int(parsed["don_checks_first_night"].get(uid))
            row.don_checks_first_night_found = _safe_int(row.don_checks_first_night_found) + _safe_int(parsed["don_checks_first_night_found"].get(uid))
            row.misses_due_to_me = _safe_int(row.misses_due_to_me) + _safe_int(parsed["misses_due_to_me"].get(uid))
            row.vote_leave_day12 = _safe_int(row.vote_leave_day12) + _safe_int(parsed["leave_vote_day12"].get(uid))
            row.farewell_total = _safe_int(row.farewell_total) + _safe_int(parsed["farewell_total"].get(uid))
            row.farewell_correct = _safe_int(row.farewell_correct) + _safe_int(parsed["farewell_correct"].get(uid))
            row.first_killed_best_move_total = _safe_int(row.first_killed_best_move_total) + _safe_int(parsed["first_killed_best_move_total"].get(uid))

            best_move_bucket: dict[int, int] = parsed["best_move_bucket"].get(uid) or {}
            row.best_move_black_0 = _safe_int(row.best_move_black_0) + _safe_int(best_move_bucket.get(0))
            row.best_move_black_1 = _safe_int(row.best_move_black_1) + _safe_int(best_move_bucket.get(1))
            row.best_move_black_2 = _safe_int(row.best_move_black_2) + _safe_int(best_move_bucket.get(2))
            row.best_move_black_3 = _safe_int(row.best_move_black_3) + _safe_int(best_move_bucket.get(3))

            if game_id > 0:
                recent = _normalize_recent(row.recent_games)
                recent.insert(
                    0,
                    {
                        "game_id": game_id,
                        "role": role or "unknown",
                        "result": result,
                        "won": won,
                        "finished_at": _to_utc_iso(finished_at),
                    },
                )
                row.recent_games = recent[:10]

    if 0 < head_id == uid:
        row.games_hosted = _safe_int(row.games_hosted) + 1


def _build_game_payload(game: Game) -> dict[str, Any] | None:
    result = _safe_str(getattr(game, "result", ""))
    if result not in FINISHED_RESULTS:
        return None

    roles = _normalize_roles(getattr(game, "roles", {}))
    players = set(roles.keys())
    head_id = _safe_int(getattr(game, "head_id", 0))
    game_id = _safe_int(getattr(game, "id", 0))
    actions = _normalize_actions(getattr(game, "actions", []))
    parsed = _parse_actions(actions, roles)

    started_at = getattr(game, "started_at", None)
    finished_at = getattr(game, "finished_at", None)
    duration_seconds = 0
    if isinstance(started_at, datetime) and isinstance(finished_at, datetime):
        try:
            duration_seconds = int((finished_at - started_at).total_seconds())
        except Exception:
            duration_seconds = 0
    if duration_seconds < 0:
        duration_seconds = 0

    return {
        "result": result,
        "roles": roles,
        "players": players,
        "head_id": head_id,
        "game_id": game_id,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "parsed": parsed,
    }


async def apply_finished_game_stats(session: AsyncSession, game: Game) -> None:
    payload = _build_game_payload(game)
    if not payload:
        return

    ids_to_update = set(payload["players"])
    head_id = _safe_int(payload["head_id"])
    if head_id > 0:
        ids_to_update.add(head_id)
    if not ids_to_update:
        return

    rows = await session.execute(select(UserGameStats).where(UserGameStats.user_id.in_(list(ids_to_update))))
    rows_map: dict[int, UserGameStats] = {int(item.user_id): item for item in rows.scalars().all()}

    for uid in ids_to_update:
        row = rows_map.get(uid)
        if not row:
            row = UserGameStats(user_id=uid)
            session.add(row)
            rows_map[uid] = row
        _apply_game_to_user_row(
            row,
            uid=uid,
            roles=payload["roles"],
            players=payload["players"],
            head_id=head_id,
            result=payload["result"],
            duration_seconds=payload["duration_seconds"],
            finished_at=payload["finished_at"],
            game_id=payload["game_id"],
            parsed=payload["parsed"],
        )


async def rebuild_user_game_stats(session: AsyncSession, user_id: int) -> UserGameStats:
    uid = _safe_int(user_id)
    if uid <= 0:
        raise ValueError("invalid user_id")

    await session.execute(delete(UserGameStats).where(UserGameStats.user_id == uid))
    row = UserGameStats(user_id=uid)
    session.add(row)

    game_rows = await session.execute(
        select(Game)
        .where(or_(Game.head_id == uid, Game.roles.has_key(str(uid))))
        .order_by(Game.finished_at.asc(), Game.id.asc())
    )

    for game in game_rows.scalars().all():
        payload = _build_game_payload(game)
        if not payload:
            continue
        _apply_game_to_user_row(
            row,
            uid=uid,
            roles=payload["roles"],
            players=payload["players"],
            head_id=payload["head_id"],
            result=payload["result"],
            duration_seconds=payload["duration_seconds"],
            finished_at=payload["finished_at"],
            game_id=payload["game_id"],
            parsed=payload["parsed"],
        )

    return row
