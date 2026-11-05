from __future__ import annotations
import json
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...models.user import User
from ...schemas.common import Identity, Ok
from ...schemas.payments import CoinInvoiceCreateIn, CoinInvoiceListOut, CoinInvoiceOut, SubscriptionPurchaseIn, SubscriptionPurchaseOut, WalletOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.payments import check_coin_invoice, create_coin_invoice, list_coin_invoices, process_kassa_webhook
from ...services.profile_theme import resolve_profile_theme_state
from ...services.wallet import buy_subscription, ensure_purchase_access, get_dc_balance

router = APIRouter()


async def purchase_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(401, detail="Unauthorized")

    await ensure_purchase_access(session, user)
    return user


@router.get("/wallet", response_model=WalletOut)
async def wallet(ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)):
    uid = int(ident["id"])
    await purchase_user(session, uid)
    state = await resolve_profile_theme_state(session, uid)
    return WalletOut(dc_balance=await get_dc_balance(session, uid), subscription_active=state.subscription_active, subscription_until=state.subscription_until)


@router.post("/coins/invoices", response_model=CoinInvoiceOut)
@log_route("payments.coins.create")
async def create_invoice(payload: CoinInvoiceCreateIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)):
    return await create_coin_invoice(session, user_id=int(ident["id"]), payload=payload)


@router.get("/coins/invoices", response_model=CoinInvoiceListOut)
async def invoices(ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)):
    uid = int(ident["id"])
    await purchase_user(session, uid)
    return await list_coin_invoices(session, user_id=uid)


@router.post("/coins/invoices/{order_id}/check", response_model=CoinInvoiceOut)
async def check_invoice(order_id: int, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)):
    uid = int(ident["id"])
    await purchase_user(session, uid)
    return await check_coin_invoice(session, user_id=uid, order_id=order_id)


@router.post("/subscriptions", response_model=SubscriptionPurchaseOut)
@log_route("payments.subscription.purchase")
async def subscription_purchase(payload: SubscriptionPurchaseIn, ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)):
    return await buy_subscription(session, user_id=int(ident["id"]), plan=payload.plan, request_id=str(payload.request_id))


@router.post("/kassa/webhook/", response_model=Ok, include_in_schema=False)
@router.post("/kassa/webhook", response_model=Ok)
@log_route("payments.kassa.webhook")
async def kassa_webhook(request: Request,
                        x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
                        x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
                        authorization: str | None = Header(default=None, alias="Authorization"),
                        session: AsyncSession = Depends(get_session)) -> Ok:
    try:
        payload = json.loads(await request.body(), parse_float=Decimal)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise HTTPException(422, detail="kassa_webhook_invalid") from exc

    if not isinstance(payload, dict):
        raise HTTPException(422, detail="kassa_webhook_invalid")

    await process_kassa_webhook(session, request=request, payload=payload, x_api_key=x_api_key,
                               x_webhook_secret=x_webhook_secret, authorization=authorization)
    return Ok()
