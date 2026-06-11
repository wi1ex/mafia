from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...schemas.common import Identity, Ok
from ...schemas.payments import LavaPaymentLinkCreateIn, LavaPaymentLinkCreateOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.payments import create_lava_payment_link, process_lava_webhook

router = APIRouter()


@router.post("/lava/link", response_model=LavaPaymentLinkCreateOut)
@log_route("payments.lava.link")
async def lava_payment_link_create(
    payload: LavaPaymentLinkCreateIn | None = Body(default=None),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> LavaPaymentLinkCreateOut:
    return await create_lava_payment_link(
        session,
        payload=payload,
        user_id=int(ident["id"]),
        username=ident["username"],
    )


@router.post("/lava/webhook/", response_model=Ok, include_in_schema=False)
@router.post("/lava/webhook", response_model=Ok)
@log_route("payments.lava.webhook")
async def lava_webhook(
    request: Request,
    payload: dict[str, Any] = Body(...),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> Ok:
    await process_lava_webhook(
        session,
        request=request,
        payload=payload,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )
    return Ok()
