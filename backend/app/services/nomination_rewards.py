from __future__ import annotations
import json
from bisect import bisect_right
from collections.abc import Mapping
from datetime import datetime, timedelta
import structlog
from fastapi import HTTPException
from sqlalchemy import select
from ..core.db import SessionLocal
from ..models.notif import Notif

log = structlog.get_logger()
MINUTES_PER_DAY = 24 * 60

NOMINATION_LEVEL_STARTS: dict[str, tuple[int, ...]] = {
    "games_played": (0, 50, 100, 250, 500, 1000, 2500, 5000),
    "games_hosted": (0, 10, 25, 50, 100, 250, 500, 1000),
    "room_minutes": tuple(days * MINUTES_PER_DAY for days in (0, 3, 7, 14, 30, 90, 180, 360)),
    "stream_minutes": (0, MINUTES_PER_DAY // 2, MINUTES_PER_DAY, 3 * MINUTES_PER_DAY,
                       7 * MINUTES_PER_DAY, 14 * MINUTES_PER_DAY, 30 * MINUTES_PER_DAY, 90 * MINUTES_PER_DAY),
    "spectator_minutes": tuple(days * MINUTES_PER_DAY for days in (0, 1, 3, 7, 14, 30, 90, 180)),
}
DEFAULT_NOMINATION_LEVELS = dict.fromkeys(NOMINATION_LEVEL_STARTS, 1)
DEFAULT_NOMINATION_LEVELS_JSON = json.dumps(DEFAULT_NOMINATION_LEVELS)


def resolve_nomination_levels(stats: Mapping[str, int]) -> dict[str, int]:
    return {key: bisect_right(starts, max(0, stats[key])) for key, starts in NOMINATION_LEVEL_STARTS.items()}


def _reward_for_levels(paid: Mapping[str, int], current: Mapping[str, int]) -> tuple[dict[str, int], int]:
    updated = {}
    coins = 0
    for key, default in DEFAULT_NOMINATION_LEVELS.items():
        previous = paid.get(key, default)
        level = max(previous, current[key])
        updated[key] = level
        coins += sum(2 * reached for reached in range(previous + 1, level + 1))
    return updated, coins


async def _grant_nomination_reward(user_id: int, current: Mapping[str, int]) -> bool:
    from ..api.utils import emit_notify
    from ..models.user import User
    from .wallet import adjust_dc_balance, sync_wallet_profile

    async with SessionLocal() as session:
        async with session.begin():
            user = await session.scalar(
                select(User).where(User.id == user_id, User.deleted_at.is_(None), User.telegram_id > 0)
                .with_for_update()
            )
            if user is None:
                return False
            updated, coins = _reward_for_levels(user.nomination_rewarded_levels, current)
            if not coins:
                return False

            operation = await adjust_dc_balance(session, user_id, coins, source="nomination_reward")
            user.nomination_rewarded_levels = updated
            note = Notif(user_id=user_id, event_key=f"dc:coin:{operation.id}", title="Баланс",
                         text=f"Поздравляем! Ваши уровни в номинациях выросли. За это вам начислено {coins} DC.")
            session.add(note)

        await emit_notify(user_id, note, kind="coins", toast={"kind": "nomination_reward"})
        try:
            await sync_wallet_profile(session, user_id, balance_only=True)
        except Exception:
            log.exception("dc.nomination_reward.profile_sync_failed", user_id=user_id)
        return True


async def grant_nomination_rewards(scheduled_at: datetime | None = None) -> int:
    from ..api.utils import build_user_mini_profile_nomination_stats_batch
    from ..models.user import User

    async with SessionLocal() as session:
        query = select(User.id, User.nomination_rewarded_levels).where(
            User.telegram_id > 0, User.deleted_at.is_(None),
        )
        if scheduled_at is not None:
            query = query.where(User.last_visit_at >= scheduled_at - timedelta(days=1))
        users = dict((await session.execute(query)).tuples().all())
        if not users:
            return 0

        stats = await build_user_mini_profile_nomination_stats_batch(session, list(users), strict_live=True)

    granted = 0
    for user_id, paid in users.items():
        current = stats[user_id].levels
        if not _reward_for_levels(paid, current)[1]:
            continue
        try:
            granted += int(await _grant_nomination_reward(user_id, current))
        except HTTPException as exc:
            if exc.detail != "dc_balance_too_large":
                raise

            log.warning("dc.nomination_reward.balance_limit", user_id=user_id)
    return granted
