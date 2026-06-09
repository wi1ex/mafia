from __future__ import annotations
import json
import re
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from secrets import compare_digest, token_urlsafe
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import structlog
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...core.db import get_session
from ...core.logging import log_action
from ...core.settings import settings
from ...models.lava_payment import LavaPayment
from ...models.subscription import UserSubscription
from ...models.user import User
from ...schemas.common import Identity, Ok
from ...schemas.payments import LavaPaymentLinkCreateOut
from ...security.auth_tokens import get_identity
from ...security.decorators import log_route
from ...services.nickname_limits import (
    SUBSCRIPTION_NICKNAME_CHANGE_LIMIT,
    normalize_nickname_changes_left,
    set_user_nickname_changes,
)
from ...services.profile_theme import (
    compute_subscription_end,
    ensure_profile_theme_defaults,
    resolve_profile_theme_state,
)
from ...services.user_cache import refresh_user_profile_cache
from ..utils import (
    emit_auth_profile_sync,
    emit_room_profile_theme_sync,
    notify_subscription_upsert,
)

router = APIRouter()
log = structlog.get_logger()

LAVA_CURRENCY = "RUB"
LAVA_MONTH_PLAN = "month"
LAVA_YEAR_PLAN = "year"
LAVA_MONTHS_BY_PLAN = {
    LAVA_MONTH_PLAN: 1,
    LAVA_YEAR_PLAN: 12,
}
LAVA_INTENT_CONTRACT_PREFIX = "intent:"
LAVA_TRACKING_TOKEN_PREFIX = "lv_"
TRACKING_TOKEN_RE = re.compile(r"^lv_[A-Za-z0-9_-]{24,96}$")
FAILURE_MARKERS = ("fail", "cancel", "refund", "chargeback", "revers")
SUCCESS_MARKERS = ("success", "paid", "complete", "completed", "succeed")


def _clean(value: object, *, max_len: int | None = None) -> str:
    text = str(value or "").strip()
    if max_len is not None:
        return text[:max_len]

    return text


def _normalize_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _normalize_status(value: object) -> str:
    return _clean(value).lower().replace("_", "-")


def _json_dumps(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    except Exception:
        return "{}"


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))

    except (InvalidOperation, ValueError, TypeError):
        return None


def _iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value

        for nested in value.values():
            yield from _iter_dicts(nested)

    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    wanted = {_normalize_key(key) for key in keys}
    for item in _iter_dicts(payload):
        for key, value in item.items():
            if _normalize_key(key) in wanted:
                return value

    return None


def _top_first_value(payload: dict[str, Any], *keys: str) -> Any:
    wanted = {_normalize_key(key) for key in keys}
    for key, value in payload.items():
        if _normalize_key(key) in wanted:
            return value

    return None


def _first_dict(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    wanted = {_normalize_key(key) for key in keys}
    for item in _iter_dicts(payload):
        for key, value in item.items():
            if _normalize_key(key) in wanted and isinstance(value, dict):
                return value

    return {}


def _extract_contract_id(payload: dict[str, Any]) -> str:
    direct = _top_first_value(
        payload,
        "contractId",
        "contract_id",
        "invoiceId",
        "invoice_id",
        "orderId",
        "order_id",
        "paymentId",
        "payment_id",
        "id",
    )
    if direct:
        return _clean(direct, max_len=128)

    for container_name in ("contract", "invoice", "order", "payment"):
        container = _first_dict(payload, container_name)
        if container:
            value = (
                container.get("contractId")
                or container.get("invoiceId")
                or container.get("orderId")
                or container.get("paymentId")
                or container.get("id")
            )
            if value:
                return _clean(value, max_len=128)

    return ""


def _extract_parent_contract_id(payload: dict[str, Any]) -> str:
    return _clean(
        _first_value(
            payload,
            "parentContractId",
            "parent_contract_id",
            "parentInvoiceId",
            "parent_invoice_id",
            "subscriptionContractId",
            "subscription_contract_id",
        ),
        max_len=128,
    )


def _extract_event_type(payload: dict[str, Any]) -> str:
    return _clean(
        _top_first_value(payload, "eventType", "event_type", "type", "event"),
        max_len=128,
    )


def _extract_buyer_email(payload: dict[str, Any]) -> str:
    buyer = _first_dict(payload, "buyer", "customer", "payer", "user")
    return _clean(
        buyer.get("email") or _first_value(payload, "buyerEmail", "customerEmail", "email"),
        max_len=254,
    )


def _extract_product(payload: dict[str, Any]) -> dict[str, Any]:
    return _first_dict(payload, "product", "productInfo", "productData")


def _extract_offer(payload: dict[str, Any]) -> dict[str, Any]:
    return _first_dict(payload, "offer", "tariff", "variant", "plan", "subscriptionPlan")


def _extract_product_id(payload: dict[str, Any]) -> str:
    product = _extract_product(payload)
    return _clean(
        product.get("id")
        or product.get("productId")
        or _first_value(payload, "productId", "product_id"),
        max_len=128,
    )


def _extract_product_title(payload: dict[str, Any]) -> str:
    product = _extract_product(payload)
    return _clean(
        product.get("title")
        or product.get("name")
        or _first_value(payload, "productTitle", "productName"),
        max_len=256,
    )


def _extract_offer_id(payload: dict[str, Any]) -> str:
    offer = _extract_offer(payload)
    return _clean(
        offer.get("id")
        or offer.get("offerId")
        or _first_value(payload, "offerId", "offer_id", "tariffId", "tariff_id", "planId"),
        max_len=128,
    )


def _extract_offer_title(payload: dict[str, Any]) -> str:
    offer = _extract_offer(payload)
    return _clean(
        offer.get("title")
        or offer.get("name")
        or _first_value(payload, "offerTitle", "offerName", "tariffTitle", "planName"),
        max_len=256,
    )


def _extract_amount_and_currency(payload: dict[str, Any]) -> tuple[Decimal | None, str]:
    for key in ("amountTotal", "amount_total", "price", "total", "paymentAmount"):
        amount_obj = _first_value(payload, key)
        if isinstance(amount_obj, dict):
            amount = _decimal_or_none(
                amount_obj.get("amount")
                or amount_obj.get("value")
                or amount_obj.get("total")
                or amount_obj.get("price")
            )
            currency = _clean(amount_obj.get("currency"), max_len=3).upper()
            if amount is not None:
                return amount, currency or LAVA_CURRENCY

    amount = _decimal_or_none(
        _first_value(payload, "amount", "sum", "totalAmount", "paidAmount", "priceAmount")
    )
    currency = _clean(_first_value(payload, "currency", "currencyCode"), max_len=3).upper()
    return amount, currency or LAVA_CURRENCY


def _plan_from_offer_id(offer_id: str) -> tuple[str, int, str] | None:
    offer = _clean(offer_id)
    if offer and settings.LAVA_MONTHLY_OFFER_ID and offer == _clean(settings.LAVA_MONTHLY_OFFER_ID):
        return LAVA_MONTH_PLAN, LAVA_MONTHS_BY_PLAN[LAVA_MONTH_PLAN], "offer_id"

    if offer and settings.LAVA_YEARLY_OFFER_ID and offer == _clean(settings.LAVA_YEARLY_OFFER_ID):
        return LAVA_YEAR_PLAN, LAVA_MONTHS_BY_PLAN[LAVA_YEAR_PLAN], "offer_id"

    return None


def _plan_text_candidates(payload: dict[str, Any], product_title: str, offer_title: str) -> str:
    parts = [product_title, offer_title]
    interesting_keys = {
        "title",
        "name",
        "description",
        "period",
        "interval",
        "duration",
        "frequency",
        "subscriptionperiod",
        "billingperiod",
        "recurringperiod",
        "plantype",
        "periodicity",
        "recurrent",
    }
    for item in _iter_dicts(payload):
        for key, value in item.items():
            if _normalize_key(key) in interesting_keys and isinstance(value, (str, int, float)):
                parts.append(str(value))
    return " ".join(part for part in parts if part).lower()


def _plan_from_text(text: str) -> tuple[str, int, str] | None:
    if re.search(r"год(овая|овой|овую|а|ом)?|year|annual|12\s*(мес|month)", text, re.I):
        return LAVA_YEAR_PLAN, LAVA_MONTHS_BY_PLAN[LAVA_YEAR_PLAN], "text"

    if re.search(r"месяц|месяч|month|monthly|1\s*(мес|month)|30\s*(дн|day)", text, re.I):
        return LAVA_MONTH_PLAN, LAVA_MONTHS_BY_PLAN[LAVA_MONTH_PLAN], "text"

    return None


def _resolve_payment_plan(payload: dict[str, Any], *, payment: LavaPayment, offer_id: str, product_title: str, offer_title: str) -> tuple[str, int, str] | None:
    if payment.plan in LAVA_MONTHS_BY_PLAN and int(payment.subscription_months or 0) > 0:
        return payment.plan, int(payment.subscription_months), "stored"

    return (
        _plan_from_offer_id(offer_id)
        or _plan_from_text(_plan_text_candidates(payload, product_title, offer_title))
    )


def _is_failure(event_type: str, status_value: str) -> bool:
    text = f"{event_type} {status_value}".lower()
    return any(marker in text for marker in FAILURE_MARKERS)


def _is_success(event_type: str, status_value: str) -> bool:
    text = f"{event_type} {status_value}".lower()
    return not _is_failure(event_type, status_value) and any(
        marker in text for marker in SUCCESS_MARKERS
    )


def _configured_product_url() -> str:
    product_url = _clean(settings.LAVA_PRODUCT_URL)
    if not product_url:
        raise HTTPException(status_code=503, detail="lava_product_missing")

    return product_url


def _configured_product_id() -> str:
    try:
        path_parts = [part for part in urlsplit(_configured_product_url()).path.split("/") if part]
    except HTTPException:
        return ""

    if len(path_parts) >= 2 and path_parts[-2] == "products":
        return _clean(path_parts[-1], max_len=128)

    return ""


def _new_tracking_token() -> str:
    return f"{LAVA_TRACKING_TOKEN_PREFIX}{token_urlsafe(24)}"


def _append_tracking_params(product_url: str, *, token: str, user_id: int) -> str:
    parts = urlsplit(product_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(
        {
            "utm_source": "mafia_site",
            "utm_medium": "subscription",
            "utm_campaign": "lava_subscription",
            "utm_content": token,
            "utm_term": str(user_id),
        }
    )
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _extract_query_value(raw_url: object, key: str) -> str:
    try:
        query = dict(parse_qsl(urlsplit(str(raw_url)).query, keep_blank_values=True))
    except Exception:
        return ""

    return _clean(query.get(key))


def _extract_utm_value(payload: dict[str, Any], key: str) -> str:
    variants = {key, key.replace("_", ""), key.replace("_", "-")}
    value = _first_value(payload, *variants)
    if value:
        return _clean(value)

    for item in _iter_dicts(payload):
        for raw_key, raw_value in item.items():
            normalized_key = _normalize_key(raw_key)
            if normalized_key in {"url", "href", "link", "paymenturl", "pageurl", "referrer"}:
                value = _extract_query_value(raw_value, key)
                if value:
                    return value
    return ""


def _extract_tracking_token(payload: dict[str, Any]) -> str:
    candidates = [
        _first_value(payload, "metadataToken", "metadata_token", "trackingToken", "tracking_token"),
        _extract_utm_value(payload, "utm_content"),
        _extract_utm_value(payload, "utm_term"),
    ]
    for candidate in candidates:
        token = _clean(candidate)
        if TRACKING_TOKEN_RE.match(token):
            return token

    return ""


def _webhook_secret() -> str:
    return _clean(settings.LAVA_WEBHOOK_SECRET)


def _bearer_token(authorization: str | None) -> str:
    value = _clean(authorization)
    if value.lower().startswith("bearer "):
        return value[7:].strip()

    return ""


def _provided_webhook_secrets(request: Request, *, x_api_key: str | None, x_webhook_secret: str | None, authorization: str | None) -> list[str]:
    return [
        value
        for value in (
            _clean(x_api_key),
            _clean(x_webhook_secret),
            _bearer_token(authorization),
            _clean(request.query_params.get("token")),
            _clean(request.query_params.get("key")),
            _clean(request.query_params.get("secret")),
        )
        if value
    ]


def _ensure_webhook_authorized(request: Request, *, x_api_key: str | None, x_webhook_secret: str | None, authorization: str | None) -> None:
    expected = _webhook_secret()
    if not expected:
        raise HTTPException(status_code=503, detail="lava_webhook_secret_missing")

    if not any(
        compare_digest(provided, expected)
        for provided in _provided_webhook_secrets(
            request,
            x_api_key=x_api_key,
            x_webhook_secret=x_webhook_secret,
            authorization=authorization,
        )
    ):
        log.warning(
            "lava.webhook.unauthorized",
            client=str(request.client.host if request.client else ""),
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


def _product_matches_expected(product_id: str) -> bool:
    expected = _configured_product_id()
    return not expected or not product_id or product_id == expected


async def _find_payment_by_contract(session: AsyncSession, contract_id: str) -> LavaPayment | None:
    if not contract_id:
        return None

    return await session.scalar(
        select(LavaPayment).where(LavaPayment.contract_id == contract_id).limit(1)
    )


async def _latest_payment_by_token(session: AsyncSession, token: str) -> LavaPayment | None:
    if not token:
        return None

    return await session.scalar(
        select(LavaPayment)
        .where(LavaPayment.metadata_token == token)
        .order_by(LavaPayment.id.desc())
        .limit(1)
    )


async def _find_or_create_payment_for_webhook(session: AsyncSession, *, contract_id: str, parent_contract_id: str, token: str, payload: dict[str, Any]) -> LavaPayment | None:
    payment = await _find_payment_by_contract(session, contract_id)
    if payment is not None:
        return payment

    parent = await _find_payment_by_contract(session, parent_contract_id)
    if parent is not None:
        payment = LavaPayment(
            contract_id=contract_id,
            parent_contract_id=parent_contract_id,
            user_id=parent.user_id,
            metadata_token=parent.metadata_token,
            email=parent.email,
            status="webhook_received",
            plan=parent.plan,
            subscription_months=parent.subscription_months,
            raw_payload=_json_dumps(payload),
        )
        session.add(payment)
        await session.flush()
        return payment

    by_token = await _latest_payment_by_token(session, token)
    if by_token is None:
        return None

    if by_token.contract_id.startswith(LAVA_INTENT_CONTRACT_PREFIX):
        by_token.contract_id = contract_id
        by_token.status = "webhook_received"
        by_token.raw_payload = _json_dumps(payload)
        return by_token

    payment = LavaPayment(
        contract_id=contract_id,
        parent_contract_id=parent_contract_id or by_token.parent_contract_id,
        user_id=by_token.user_id,
        metadata_token=token,
        email=by_token.email,
        status="webhook_received",
        plan=by_token.plan,
        subscription_months=by_token.subscription_months,
        raw_payload=_json_dumps(payload),
    )
    session.add(payment)
    await session.flush()
    return payment


async def _grant_subscription_for_payment(session: AsyncSession, payment: LavaPayment) -> bool:
    uid = int(payment.user_id or 0)
    months = int(payment.subscription_months or 0)
    if uid <= 0 or months <= 0:
        return False

    user = await session.get(User, uid)
    if not user or user.deleted_at is not None:
        return False

    now = datetime.now(timezone.utc)
    subscription = await session.scalar(
        select(UserSubscription).where(UserSubscription.user_id == uid).limit(1)
    )

    had_active_subscription = bool(
        subscription is not None and subscription.starts_at <= now < subscription.ends_at
    )
    issue_nickname_limit = False
    if subscription is None:
        subscription = UserSubscription(
            user_id=uid,
            starts_at=now,
            ends_at=compute_subscription_end(now, months=months),
        )
        session.add(subscription)
        issue_nickname_limit = True
    elif had_active_subscription:
        subscription.ends_at = compute_subscription_end(subscription.ends_at, months=months)
        user.nickname_changes_left = normalize_nickname_changes_left(user.nickname_changes_left)
    else:
        subscription.starts_at = now
        subscription.ends_at = compute_subscription_end(now, months=months)
        issue_nickname_limit = True

    if issue_nickname_limit:
        set_user_nickname_changes(user, SUBSCRIPTION_NICKNAME_CHANGE_LIMIT)

    await ensure_profile_theme_defaults(session, uid, now=now)
    payment.processed_at = now
    payment.status = "processed"
    await session.commit()
    await session.refresh(subscription)
    await refresh_user_profile_cache(session, uid)
    theme_state = await resolve_profile_theme_state(session, uid)

    with suppress(Exception):
        await emit_auth_profile_sync(uid, role=str(user.role))
    with suppress(Exception):
        await emit_room_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        from ...services.global_chat import emit_global_chat_profile_theme_sync

        await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        await notify_subscription_upsert(
            session,
            user,
            subscription,
            extended=had_active_subscription,
        )

    await log_action(
        session,
        user_id=uid,
        username=str(user.username or f"user{uid}"),
        action="lava_subscription_grant",
        details={
            "contract_id": payment.contract_id,
            "parent_contract_id": payment.parent_contract_id,
            "plan": payment.plan,
            "months": months,
            "offer_id": payment.offer_id,
            "amount": str(payment.amount) if payment.amount is not None else None,
            "currency": payment.currency,
            "ends_at": subscription.ends_at.isoformat(),
        },
    )
    return True


@router.post("/lava/link", response_model=LavaPaymentLinkCreateOut)
@log_route("payments.lava.link")
async def lava_payment_link_create(ident: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)) -> LavaPaymentLinkCreateOut:
    uid = int(ident["id"])
    user = await session.get(User, uid)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    token = _new_tracking_token()
    payment_url = _append_tracking_params(_configured_product_url(), token=token, user_id=uid)
    payment = LavaPayment(
        contract_id=f"{LAVA_INTENT_CONTRACT_PREFIX}{token}",
        user_id=uid,
        metadata_token=token,
        status="link_created",
        payment_url=payment_url,
        raw_payload=_json_dumps({"kind": "lava_product_link", "utm_content": token}),
    )
    session.add(payment)
    await session.commit()

    await log_action(
        session,
        user_id=uid,
        username=str(user.username or ident["username"] or f"user{uid}"),
        action="lava_payment_link_create",
        details={"payment_id": payment.id, "product_id": _configured_product_id()},
    )

    return LavaPaymentLinkCreateOut(payment_url=payment_url)


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
    _ensure_webhook_authorized(
        request,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )

    contract_id = _extract_contract_id(payload)
    parent_contract_id = _extract_parent_contract_id(payload)
    token = _extract_tracking_token(payload)
    event_type = _extract_event_type(payload)
    status_value = _normalize_status(
        _top_first_value(payload, "status", "paymentStatus", "state")
    )
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id_missing")

    payment = await _find_or_create_payment_for_webhook(
        session,
        contract_id=contract_id,
        parent_contract_id=parent_contract_id,
        token=token,
        payload=payload,
    )
    if payment is None:
        log.warning(
            "lava.webhook.unknown_contract",
            contract_id=contract_id,
            parent_contract_id=parent_contract_id,
            event_type=event_type,
            has_token=bool(token),
        )
        return Ok()

    amount, currency = _extract_amount_and_currency(payload)
    product_id = _extract_product_id(payload)
    product_title = _extract_product_title(payload)
    offer_id = _extract_offer_id(payload)
    offer_title = _extract_offer_title(payload)

    payment.parent_contract_id = parent_contract_id or payment.parent_contract_id
    payment.metadata_token = token or payment.metadata_token
    payment.email = _extract_buyer_email(payload) or payment.email
    payment.event_type = event_type or payment.event_type
    payment.status = status_value or event_type or payment.status
    payment.product_id = product_id or payment.product_id
    payment.product_title = product_title or payment.product_title
    payment.offer_id = offer_id or payment.offer_id
    payment.offer_title = offer_title or payment.offer_title
    payment.amount = amount or payment.amount
    payment.currency = currency or payment.currency
    payment.raw_payload = _json_dumps(payload)

    resolved_plan = _resolve_payment_plan(
        payload,
        payment=payment,
        offer_id=offer_id or payment.offer_id or "",
        product_title=product_title or payment.product_title or "",
        offer_title=offer_title or payment.offer_title or "",
    )
    if resolved_plan is not None:
        plan, months, reason = resolved_plan
        payment.plan = plan
        payment.subscription_months = months
        log.info(
            "lava.webhook.plan_resolved",
            contract_id=contract_id,
            plan=plan,
            months=months,
            reason=reason,
        )

    if not _product_matches_expected(product_id):
        payment.status = "product_mismatch"
        log.warning(
            "lava.webhook.product_mismatch",
            contract_id=contract_id,
            expected_product_id=_configured_product_id(),
            actual_product_id=product_id,
        )
        await session.commit()
        return Ok()

    if _is_failure(event_type, status_value):
        await session.commit()
        return Ok()

    if payment.processed_at is not None:
        await session.commit()
        return Ok()

    if _is_success(event_type, status_value):
        granted = await _grant_subscription_for_payment(session, payment)
        if not granted:
            log.warning(
                "lava.webhook.grant_skipped",
                contract_id=contract_id,
                user_id=payment.user_id,
                plan=payment.plan,
                months=payment.subscription_months,
                offer_id=payment.offer_id,
                amount=str(payment.amount) if payment.amount is not None else None,
                currency=payment.currency,
            )
            await session.commit()
        return Ok()

    await session.commit()
    return Ok()
