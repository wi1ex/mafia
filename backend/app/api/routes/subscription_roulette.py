from __future__ import annotations
from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...schemas.common import Identity
from ...schemas.subscription_roulette import (
    SubscriptionRouletteSpinIn,
    SubscriptionRouletteSpinOut,
    SubscriptionRouletteStatusOut,
)
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route, rate_limited
from ...services.subscription_roulette import (
    get_roulette_status,
    deliver_roulette_win,
    spin_roulette,
)

router = APIRouter()


@router.get("/status", response_model=SubscriptionRouletteStatusOut)
@log_route("users.subscription_roulette.status")
@rate_limited(lambda ident, **_: f"rl:subscription_roulette_status:{ident['id']}", limit=10, window_s=1)
async def roulette_status(
    round_id: int | None = Query(default=None, ge=0, le=9223372036854775807),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionRouletteStatusOut:
    return await get_roulette_status(session, int(ident["id"]), round_id=round_id)


@router.post("/spin", response_model=SubscriptionRouletteSpinOut)
@log_route("users.subscription_roulette.spin")
@rate_limited(lambda ident, **_: f"rl:subscription_roulette_spin:{ident['id']}", limit=5, window_s=1)
async def roulette_spin(
    background_tasks: BackgroundTasks,
    payload: SubscriptionRouletteSpinIn | None = Body(default=None),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionRouletteSpinOut:
    result = await spin_roulette(session, int(ident["id"]), round_id=payload.round_id if payload is not None else None)
    if result.created:
        background_tasks.add_task(deliver_roulette_win, result)
    return result.response
