from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...schemas.common import Identity, Ok
from ...schemas.payments import LavaPaymentLinkCreateIn, LavaPaymentLinkCreateOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services import payments as payment_service

router = APIRouter()


@router.post("/lava/link", response_model=LavaPaymentLinkCreateOut)
@log_route("payments.lava.link")
async def lava_payment_link_create(
    payload: LavaPaymentLinkCreateIn | None = Body(default=None),
    ident: Identity = Depends(get_identity),
    session: AsyncSession = Depends(get_session),
) -> LavaPaymentLinkCreateOut:
    uid = int(ident["id"])
    user = await session.get(payment_service.User, uid)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    plan = payment_service._normalize_plan(payload.plan if payload is not None else None)
    email = payment_service._normalize_buyer_email(
        payload.email if payload is not None else None
    )
    requested_currency, payment_provider, payment_method, promo_code = (
        payment_service._normalize_invoice_options(payload)
    )
    offer_id, months = payment_service._configured_offer_for_plan(plan)
    token = payment_service._new_tracking_token()
    invoice_request = payment_service._invoice_request_payload(
        email=email,
        offer_id=offer_id,
        currency=requested_currency,
        payment_provider=payment_provider,
        payment_method=payment_method,
        promo_code=promo_code,
        token=token,
        user_id=uid,
    )
    log_username = payment_service._user_log_username(user, ident["username"])
    await payment_service._log_lava_event(
        session,
        event="pay_clicked",
        user_id=uid,
        username=log_username,
        email=email,
        plan=plan,
        months=months,
        currency=requested_currency,
        offer_id=offer_id,
        payment_provider=payment_provider,
        payment_method=payment_method,
        promo_code=promo_code,
    )
    try:
        invoice = await payment_service._create_lava_invoice(invoice_request)
    except HTTPException as exc:
        await payment_service._log_lava_event(
            session,
            event="payment_link_failed",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            offer_id=offer_id,
            reason=exc.detail,
        )
        raise

    contract_id = payment_service._clean(invoice.get("id"), max_len=128)
    payment_url = payment_service._clean(invoice.get("paymentUrl"))
    if not contract_id:
        payment_service.log.warning(
            "lava.invoice.contract_id_missing",
            response=payment_service._json_dumps(invoice)[:1000],
        )
        await payment_service._log_lava_event(
            session,
            event="payment_link_failed",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            offer_id=offer_id,
            reason="lava_contract_id_missing",
        )
        raise HTTPException(status_code=502, detail="lava_contract_id_missing")

    amount, invoice_currency = payment_service._extract_amount_and_currency(invoice)
    if not payment_url and not payment_service._is_zero_amount(amount):
        payment_service.log.warning(
            "lava.invoice.payment_url_missing",
            contract_id=contract_id,
            response=payment_service._json_dumps(invoice)[:1000],
        )
        await payment_service._log_lava_event(
            session,
            event="payment_link_failed",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            offer_id=offer_id,
            contract_id=contract_id,
            reason="lava_payment_url_missing",
        )
        raise HTTPException(status_code=502, detail="lava_payment_url_missing")

    payment = payment_service.LavaPayment(
        contract_id=contract_id,
        user_id=uid,
        metadata_token=token,
        email=email,
        status=payment_service._normalize_status(invoice.get("status")) or "invoice_created",
        offer_id=offer_id,
        plan=plan,
        amount=amount,
        currency=invoice_currency or requested_currency,
        subscription_months=months,
        payment_url=payment_url,
        raw_payload=payment_service._json_dumps(
            {
                "kind": "lava_invoice",
                "request": {**invoice_request, "email": email},
                "response": invoice,
            }
        ),
    )
    session.add(payment)
    processed = False
    if payment_url:
        await session.commit()
    else:
        await session.flush()
        processed = await payment_service._grant_subscription_for_payment(session, payment)
        if not processed:
            await payment_service._log_lava_event(
                session,
                event="subscription_grant_skipped",
                user_id=uid,
                username=log_username,
                contract_id=contract_id,
                plan=plan,
                months=months,
                reason="free_invoice_not_processed",
                commit=False,
            )
            await session.commit()
            raise HTTPException(status_code=502, detail="lava_free_invoice_not_processed")

    await payment_service._log_lava_event(
        session,
        event="payment_link_created",
        user_id=uid,
        username=log_username,
        payment_id=payment.id,
        contract_id=contract_id,
        plan=plan,
        months=months,
        offer_id=offer_id,
        currency=requested_currency,
        invoice_currency=invoice_currency,
        payment_provider=payment_provider,
        payment_method=payment_method,
        promo_code=promo_code,
        amount=payment.amount,
        payment_url_created=bool(payment_url),
        processed=processed,
        result="subscription_granted_without_payment_url" if processed else "payment_url_created",
    )

    return LavaPaymentLinkCreateOut(
        payment_url=payment_url,
        contract_id=contract_id,
        processed=processed,
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
    payment_service._ensure_webhook_authorized(
        request,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )

    contract_id = payment_service._extract_contract_id(payload)
    token = payment_service._extract_tracking_token(payload)
    tracking_user_id = payment_service._extract_tracking_user_id(payload)
    event_type = payment_service._extract_event_type(payload)
    status_value = payment_service._normalize_status(payload.get("status"))
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id_missing")

    payment = await payment_service._find_or_create_payment_for_webhook(
        session,
        contract_id=contract_id,
        token=token,
        user_id=tracking_user_id,
        payload=payload,
    )
    amount, currency = payment_service._extract_amount_and_currency(payload)
    product_id = payment_service._extract_product_id(payload)
    product_title = payment_service._extract_product_title(payload)

    payment.metadata_token = token or payment.metadata_token
    payment.email = payment_service._extract_buyer_email(payload) or payment.email
    payment.event_type = event_type or payment.event_type
    payment.status = status_value or event_type or payment.status
    payment.product_id = product_id or payment.product_id
    payment.product_title = product_title or payment.product_title
    payment.amount = amount if amount is not None else payment.amount
    payment.currency = currency or payment.currency
    payment.raw_payload = payment_service._json_dumps(payload)

    if not payment_service._product_matches_expected(product_id):
        payment.status = "product_mismatch"
        expected_product_id = payment_service._configured_product_id()
        payment_service.log.warning(
            "lava.webhook.product_mismatch",
            contract_id=contract_id,
            expected_product_id=expected_product_id,
            actual_product_id=product_id,
        )
        await payment_service._log_lava_event(
            session,
            event="webhook_product_mismatch",
            user_id=payment.user_id,
            username=payment_service._payment_log_username(payment),
            **payment_service._webhook_log_fields(
                payment,
                contract_id=contract_id,
                event_type=event_type,
                status_value=status_value,
                expected_product_id=expected_product_id,
            ),
            commit=False,
        )
        await session.commit()
        return Ok()

    if payment_service._is_ignored_lava_event(event_type):
        await payment_service._log_lava_event(
            session,
            event="webhook_ignored",
            user_id=payment.user_id,
            username=payment_service._payment_log_username(payment),
            **payment_service._webhook_log_fields(
                payment,
                contract_id=contract_id,
                event_type=event_type,
                status_value=status_value,
                reason="recurring_not_supported",
            ),
            commit=False,
        )
        await session.commit()
        return Ok()

    if payment_service._is_lava_payment_failure(event_type, status_value):
        await payment_service._log_lava_event(
            session,
            event="webhook_failed",
            user_id=payment.user_id,
            username=payment_service._payment_log_username(payment),
            **payment_service._webhook_log_fields(
                payment,
                contract_id=contract_id,
                event_type=event_type,
                status_value=status_value,
            ),
            commit=False,
        )
        await session.commit()
        return Ok()

    if payment.processed_at is not None:
        await payment_service._log_lava_event(
            session,
            event="webhook_duplicate",
            user_id=payment.user_id,
            username=payment_service._payment_log_username(payment),
            **payment_service._webhook_log_fields(
                payment,
                contract_id=contract_id,
                event_type=event_type,
                status_value=status_value,
                processed_at=payment.processed_at,
            ),
            commit=False,
        )
        await session.commit()
        return Ok()

    if payment_service._is_lava_payment_success(event_type, status_value):
        await payment_service._log_lava_event(
            session,
            event="webhook_paid",
            user_id=payment.user_id,
            username=payment_service._payment_log_username(payment),
            **payment_service._webhook_log_fields(
                payment,
                contract_id=contract_id,
                event_type=event_type,
                status_value=status_value,
            ),
            commit=False,
        )
        granted = await payment_service._grant_subscription_for_payment(session, payment)
        if not granted:
            payment_service.log.warning(
                "lava.webhook.grant_skipped",
                contract_id=contract_id,
                user_id=payment.user_id,
                plan=payment.plan,
                months=payment.subscription_months,
                offer_id=payment.offer_id,
                amount=str(payment.amount) if payment.amount is not None else None,
                currency=payment.currency,
            )
            await payment_service._log_lava_event(
                session,
                event="subscription_grant_skipped",
                user_id=payment.user_id,
                username=payment_service._payment_log_username(payment),
                contract_id=contract_id,
                plan=payment.plan,
                months=payment.subscription_months,
                reason="user_or_subscription_period_missing",
                commit=False,
            )
            await session.commit()
        return Ok()

    await payment_service._log_lava_event(
        session,
        event="webhook_unhandled",
        user_id=payment.user_id,
        username=payment_service._payment_log_username(payment),
        **payment_service._webhook_log_fields(
            payment,
            contract_id=contract_id,
            event_type=event_type,
            status_value=status_value,
        ),
        commit=False,
    )
    await session.commit()
    return Ok()
