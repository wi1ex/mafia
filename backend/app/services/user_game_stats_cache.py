from __future__ import annotations
import hashlib
import json
import structlog
from typing import Any, Iterable
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.clients import get_redis
from ..models.friend import FriendCloseness
from ..models.game import Game
from ..schemas.user import UserGameStatsOut, UserBestMoveStatsOut, UserTopPlayerOut
from ..security.parameters import get_cached_settings
from ..services.game_stats import build_user_game_stats_row
from ..services.user_cache import get_user_profiles_cached

log = structlog.get_logger()

TOP_PLAYERS_LIMIT = 5
CACHE_VERSION = 1


def season_bounds(starts: list[int] | tuple[int, ...], season_index: int) -> tuple[int, int | None]:
    season_no = int(season_index)
    if season_no < 1:
        raise ValueError("season_index_invalid")

    normalized = tuple(sorted(set(int(v) for v in starts if int(v) > 0)))
    if not normalized:
        raise ValueError("season_starts_empty")

    if season_no > len(normalized):
        raise ValueError("season_index_out_of_range")

    start = normalized[season_no - 1]
    end: int | None = None
    if season_no < len(normalized):
        end = max(start, normalized[season_no] - 1)
    return start, end


def _safe_int(raw: Any) -> int:
    if raw is None:
        return 0

    try:
        return int(raw)

    except Exception:
        return 0


def _pct(part: int, total: int) -> float:
    p = _safe_int(part)
    t = _safe_int(total)
    if p <= 0 or t <= 0:
        return 0.0

    return round((p / t) * 100, 2)


def _settings_hash() -> str:
    season_csv = str(get_cached_settings().season_start_game_number or "1")
    return hashlib.sha1(season_csv.encode("utf-8")).hexdigest()[:12]


def _cache_key(user_id: int, season: int | None) -> str:
    season_part = "all" if season is None else f"s{int(season)}"
    return f"user:{int(user_id)}:stats:game:v{CACHE_VERSION}:{_settings_hash()}:{season_part}"


def _normalize_user_ids(user_ids: Iterable[int | str]) -> list[int]:
    ids: set[int] = set()
    for raw in user_ids:
        try:
            uid = int(raw)
        except Exception:
            continue
        if uid > 0:
            ids.add(uid)
    return sorted(ids)


def _build_game_stats(stats_row: dict[str, int], top_players: list[UserTopPlayerOut]) -> UserGameStatsOut:
    games_played = _safe_int(stats_row.get("games_decisive"))
    games_won = _safe_int(stats_row.get("games_won"))
    don_games = _safe_int(stats_row.get("don_games"))
    don_checks_first_night_found = _safe_int(stats_row.get("don_checks_first_night_found"))
    vote_leave_day12 = _safe_int(stats_row.get("vote_leave_day12"))
    foul_removed_count = _safe_int(stats_row.get("foul_removed_count"))
    vote_for_red_on_black_win_count = _safe_int(stats_row.get("vote_for_red_on_black_win_count"))
    farewell_total = _safe_int(stats_row.get("farewell_total"))
    farewell_correct = _safe_int(stats_row.get("farewell_correct"))

    return UserGameStatsOut(
        games_played=games_played,
        games_won=games_won,
        winrate_percent=_pct(games_won, games_played),
        games_hosted=_safe_int(stats_row.get("games_hosted")),
        don_first_night_find_count=don_checks_first_night_found,
        don_first_night_find_percent=_pct(don_checks_first_night_found, don_games),
        vote_leave_day12_count=vote_leave_day12,
        vote_leave_day12_percent=_pct(vote_leave_day12, games_played),
        foul_removed_count=foul_removed_count,
        foul_removed_percent=_pct(foul_removed_count, games_played),
        vote_for_red_on_black_win_count=vote_for_red_on_black_win_count,
        farewell_total=farewell_total,
        farewell_success_percent=_pct(farewell_correct, farewell_total),
        best_win_streak=_safe_int(stats_row.get("best_win_streak")),
        best_loss_streak=_safe_int(stats_row.get("best_loss_streak")),
        role_citizen={
            "games": _safe_int(stats_row.get("citizen_games")),
            "wins": _safe_int(stats_row.get("citizen_wins")),
            "winrate_percent": _pct(_safe_int(stats_row.get("citizen_wins")), _safe_int(stats_row.get("citizen_games"))),
        },
        role_sheriff={
            "games": _safe_int(stats_row.get("sheriff_games")),
            "wins": _safe_int(stats_row.get("sheriff_wins")),
            "winrate_percent": _pct(_safe_int(stats_row.get("sheriff_wins")), _safe_int(stats_row.get("sheriff_games"))),
        },
        role_don={
            "games": _safe_int(stats_row.get("don_games")),
            "wins": _safe_int(stats_row.get("don_wins")),
            "winrate_percent": _pct(_safe_int(stats_row.get("don_wins")), _safe_int(stats_row.get("don_games"))),
        },
        role_mafia={
            "games": _safe_int(stats_row.get("mafia_games")),
            "wins": _safe_int(stats_row.get("mafia_wins")),
            "winrate_percent": _pct(_safe_int(stats_row.get("mafia_wins")), _safe_int(stats_row.get("mafia_games"))),
        },
        best_move=UserBestMoveStatsOut(
            first_killed_total=_safe_int(stats_row.get("first_killed_best_move_total")),
            marks_black_0=_safe_int(stats_row.get("best_move_black_0")),
            marks_black_1=_safe_int(stats_row.get("best_move_black_1")),
            marks_black_2=_safe_int(stats_row.get("best_move_black_2")),
            marks_black_3=_safe_int(stats_row.get("best_move_black_3")),
        ),
        top_players=top_players,
    )


async def _build_top_players_all(session: AsyncSession, uid: int) -> list[UserTopPlayerOut]:
    closeness_rows = await session.execute(
        select(FriendCloseness.user_low, FriendCloseness.user_high, FriendCloseness.games_together)
        .where(
            or_(FriendCloseness.user_low == uid, FriendCloseness.user_high == uid),
            FriendCloseness.games_together > 0,
        )
        .order_by(FriendCloseness.games_together.desc(), FriendCloseness.updated_at.desc(), FriendCloseness.id.desc())
        .limit(TOP_PLAYERS_LIMIT)
    )

    top_ids: list[int] = []
    top_games: dict[int, int] = {}
    for user_low, user_high, games_together in closeness_rows.all():
        lo = int(user_low)
        hi = int(user_high)
        other_id = hi if lo == uid else lo
        if other_id <= 0 or other_id in top_games:
            continue
        top_ids.append(other_id)
        top_games[other_id] = max(0, int(games_together or 0))
        if len(top_ids) >= TOP_PLAYERS_LIMIT:
            break

    if not top_ids:
        return []

    profiles = await get_user_profiles_cached(session, set(top_ids))
    out: list[UserTopPlayerOut] = []
    for other_id in top_ids:
        profile = profiles.get(other_id) or {}
        username_raw = profile.get("username")
        username = str(username_raw) if isinstance(username_raw, str) else None
        out.append(
            UserTopPlayerOut(
                id=other_id,
                username=username,
                games_together=top_games.get(other_id, 0),
            )
        )
    return out


async def _build_top_players_season(session: AsyncSession, uid: int, *, game_id_min: int, game_id_max: int | None = None) -> list[UserTopPlayerOut]:
    filters = [Game.roles.has_key(str(uid)), Game.id >= int(game_id_min)]
    if game_id_max is not None and int(game_id_max) > 0:
        filters.append(Game.id <= int(game_id_max))

    rows = await session.execute(select(Game.roles).where(*filters).order_by(Game.id.asc()))
    games_together: dict[int, int] = {}
    for roles_raw in rows.scalars().all():
        if not isinstance(roles_raw, dict):
            continue
        players: set[int] = set()
        for raw_uid in roles_raw.keys():
            player_id = _safe_int(raw_uid)
            if player_id > 0:
                players.add(player_id)
        if uid not in players:
            continue
        players.discard(uid)
        for other_id in players:
            games_together[other_id] = games_together.get(other_id, 0) + 1

    if not games_together:
        return []

    top_pairs = sorted(games_together.items(), key=lambda item: (-item[1], item[0]))[:TOP_PLAYERS_LIMIT]
    profile_ids = {other_id for other_id, _ in top_pairs}
    profiles = await get_user_profiles_cached(session, profile_ids) if profile_ids else {}

    top_players: list[UserTopPlayerOut] = []
    for other_id, games_count in top_pairs:
        profile = profiles.get(other_id) or {}
        username_raw = profile.get("username")
        username = str(username_raw) if isinstance(username_raw, str) else None
        top_players.append(
            UserTopPlayerOut(
                id=other_id,
                username=username,
                games_together=max(0, int(games_count)),
            )
        )
    return top_players


def _normalize_season_or_raise(season: int | None) -> int | None:
    if season is None:
        return None

    season_no = _safe_int(season)
    if season_no < 1:
        raise ValueError("season_invalid")

    starts = get_cached_settings().season_start_game_numbers
    try:
        season_bounds(starts, season_no)
    except ValueError as exc:
        raise ValueError("season_not_found") from exc

    return season_no


async def _compute_user_game_stats(session: AsyncSession, user_id: int, season: int | None) -> UserGameStatsOut:
    uid = _safe_int(user_id)
    if uid <= 0:
        raise ValueError("invalid_user_id")

    season_no = _normalize_season_or_raise(season)
    if season_no is None:
        stats_row = await build_user_game_stats_row(session, uid)
        top_players = await _build_top_players_all(session, uid)
        return _build_game_stats(stats_row, top_players)

    starts = get_cached_settings().season_start_game_numbers
    start_id, end_id = season_bounds(starts, season_no)
    stats_row = await build_user_game_stats_row(session, uid, game_id_min=start_id, game_id_max=end_id)
    top_players = await _build_top_players_season(session, uid, game_id_min=start_id, game_id_max=end_id)
    return _build_game_stats(stats_row, top_players)


async def _read_cached_game_stats(user_id: int, season: int | None) -> UserGameStatsOut | None:
    key = _cache_key(user_id, season)
    r = get_redis()
    try:
        raw = await r.get(key)
    except Exception:
        return None

    if not raw:
        return None

    try:
        payload = json.loads(str(raw))
        return UserGameStatsOut.model_validate(payload)

    except Exception:
        try:
            await r.delete(key)
        except Exception:
            pass
        return None


async def _write_cached_game_stats(user_id: int, season: int | None, game_stats: UserGameStatsOut) -> None:
    key = _cache_key(user_id, season)
    r = get_redis()
    try:
        raw = json.dumps(game_stats.model_dump(), ensure_ascii=False, separators=(",", ":"))
        await r.set(key, raw)
    except Exception:
        log.warning("user_stats_cache.write_failed", user_id=int(user_id), season=season if season is not None else "all")


async def get_user_game_stats_cached(session: AsyncSession, user_id: int, season: int | None) -> UserGameStatsOut:
    season_no = _normalize_season_or_raise(season)
    cached = await _read_cached_game_stats(user_id, season_no)
    if cached:
        return cached

    game_stats = await _compute_user_game_stats(session, user_id, season_no)
    await _write_cached_game_stats(user_id, season_no, game_stats)
    return game_stats


async def warm_user_game_stats_cache_for_users(session: AsyncSession, user_ids: Iterable[int | str]) -> None:
    ids = _normalize_user_ids(user_ids)
    if not ids:
        return

    starts = get_cached_settings().season_start_game_numbers
    current_season = max(1, len(starts))
    seasons: list[int | None] = [None, current_season]

    for uid in ids:
        for season in seasons:
            try:
                game_stats = await _compute_user_game_stats(session, uid, season)
                await _write_cached_game_stats(uid, season, game_stats)
            except Exception:
                log.warning("user_stats_cache.warm_failed", user_id=uid, season=season if season is not None else "all")
