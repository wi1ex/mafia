from __future__ import annotations
from contextlib import suppress
from math import ceil
from datetime import datetime
import structlog
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.game import Game
from ..models.notif import Notif
from .game_scoring import RATING_MODE
from .wallet import adjust_dc_balance, lock_user_balance, sync_wallet_profile


def rounded_game_minutes(started_at: datetime, finished_at: datetime) -> int:
    return max(0, ceil((finished_at - started_at).total_seconds() / 60))


async def reward_rating_host(session: AsyncSession, game: Game) -> Notif | None:
    if game.mode != RATING_MODE or not game.head_id:
        return None

    try:
        user = await lock_user_balance(session, int(game.head_id))
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise

    if user.deleted_at is not None:
        return None
    await session.refresh(game, attribute_names=["host_reward_minutes"])
    if game.host_reward_minutes is not None:
        return None
    game.host_reward_minutes = rounded_game_minutes(game.started_at, game.finished_at)
    user.rating_host_minutes += game.host_reward_minutes
    coins = max(0, user.rating_host_minutes // 60 - user.rating_host_reward_days)
    await session.flush()
    if not coins:
        return None
    try:
        async with session.begin_nested():
            operation = await adjust_dc_balance(session, int(user.id), coins, source="game_reward", request_id=f"rating_game:{game.id}")
            user.rating_host_reward_days += coins
            note = Notif(user_id=user.id, event_key=f"dc:coin:{operation.id}", title="Награда за проведение игр",
                         text=f"За проведение рейтинговых игр начислено {coins} DC. Баланс: {operation.balance_after} DC.")
            session.add(note)
            await session.flush()
        return note
    except Exception:
        structlog.get_logger().exception("dc.rating_host_grant_failed", game_id=game.id, quantity=coins)
        return None


async def sync_rating_host_subscription(session: AsyncSession, user_id: int, note: Notif) -> None:
    from ..api.utils import emit_notify
    with suppress(Exception):
        await emit_notify(user_id, note, kind="coins", toast={"kind": "game_reward"})
    with suppress(Exception):
        await sync_wallet_profile(session, user_id)
