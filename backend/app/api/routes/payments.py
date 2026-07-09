from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Body, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...schemas.common import Identity, Ok
from ...schemas.payments import KassaPaymentLinkCreateIn, KassaPaymentLinkCreateOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.payments import create_kassa_payment_link, process_kassa_webhook

router = APIRouter()


@router.post("/kassa/link", response_model=KassaPaymentLinkCreateOut)
@log_route("payments.kassa.link")
async def kassa_payment_link_create(
    payload: KassaPaymentLinkCreateIn | None = Body(default=None),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> KassaPaymentLinkCreateOut:
    return await create_kassa_payment_link(
        session,
        payload=payload,
        user_id=int(ident["id"]),
        username=ident["username"],
    )


@router.post("/kassa/webhook/", response_model=Ok, include_in_schema=False)
@router.post("/kassa/webhook", response_model=Ok)
@log_route("payments.kassa.webhook")
async def kassa_webhook(
    request: Request,
    payload: dict[str, Any] = Body(...),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_session),
) -> Ok:
    await process_kassa_webhook(
        session,
        request=request,
        payload=payload,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )
    return Ok()
