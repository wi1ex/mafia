from __future__ import annotations
import base64
import binascii
import json
import re
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from secrets import compare_digest, token_urlsafe
from typing import Any
from urllib.parse import urlsplit
import httpx
import structlog
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.logging import log_action
from ..core.settings import settings
from ..models.lava_payment import LavaPayment
from ..models.subscription import UserSubscription
from ..models.user import User
from ..schemas.payments import LavaPaymentLinkCreateIn
from .nickname_limits import (
    SUBSCRIPTION_NICKNAME_CHANGE_LIMIT,
    normalize_nickname_changes_left,
    set_user_nickname_changes,
)
from .profile_theme import (
    compute_subscription_end,
    ensure_profile_theme_defaults,
    resolve_profile_theme_state,
)
from .user_cache import refresh_user_profile_cache
from ..api.utils import (
    emit_auth_profile_sync,
    emit_room_profile_theme_sync,
    notify_subscription_upsert,
)

log = structlog.get_logger()

LAVA_CURRENCY = "RUB"
LAVA_API_BASE_URL = "https://gate.lava.top"
LAVA_INVOICE_PATH = "/api/v3/invoice"
LAVA_BUYER_LANGUAGE = "RU"
LAVA_REQUEST_TIMEOUT_SECONDS = 15
LAVA_CURRENCIES = {"RUB", "USD", "EUR"}
LAVA_PAYMENT_PROVIDERS = {"SMART_GLOCAL", "PAY2ME"}
LAVA_PAYMENT_METHODS = {"CARD", "SBP"}
LAVA_MONTH_PLAN = "month"
LAVA_YEAR_PLAN = "year"
LAVA_MONTHS_BY_PLAN = {
    LAVA_MONTH_PLAN: 1,
    LAVA_YEAR_PLAN: 12,
}
LAVA_TRACKING_TOKEN_PREFIX = "lv_"
TRACKING_TOKEN_RE = re.compile(r"^lv_[A-Za-z0-9_-]{24,96}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
PROMO_CODE_RE = re.compile(r"^[A-Z0-9_-]{3,36}$")
LAVA_PROMO_REJECTION_RE = re.compile(r"promo|promocode|coupon|discount|промо|скид", re.I)
LAVA_PROMO_USAGE_LIMIT_RE = re.compile(r"usage\s+limit|limit.*exceed|лимит|исчерпан", re.I)
LAVA_PAYMENT_SUCCESS_EVENT = "payment.success"
LAVA_PAYMENT_FAILED_EVENT = "payment.failed"
LAVA_PAYMENT_FAILED_STATUSES = {"failed", "cancelled", "refunded", "chargeback"}
LAVA_IGNORED_EVENTS = {
    "subscription.recurring.payment.success",
    "subscription.recurring.payment.failed",
    "subscription.cancelled",
}
LAVA_LOG_ACTION = "lava_payment"


def _clean(value: object, *, max_len: int | None = None) -> str:
    text = str(value or "").strip()
    if max_len is not None:
        return text[:max_len]

    return text


def _normalize_status(value: object) -> str:
    return _clean(value).lower().replace("_", "-")


def _json_dumps(payload: Any) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    except Exception:
        return "{}"


def _log_value(value: object) -> str:
    if value is None or value == "":
        return "-"

    if isinstance(value, datetime):
        return value.isoformat()

    text = str(value).replace("\n", " ").strip()
    return text or "-"


def _log_details(event: str, **fields: object) -> str:
    parts = [f"event={event}"]
    parts.extend(f"{key}={_log_value(value)}" for key, value in fields.items())
    return " ".join(parts)


async def _log_lava_event(session: AsyncSession, *, event: str, user_id: int | None, username: str | None, commit: bool = True, **fields: object) -> None:
    await log_action(
        session,
        user_id=user_id,
        username=username,
        action=LAVA_LOG_ACTION,
        details=_log_details(event, **fields),
        commit=commit,
    )


def _user_log_username(user: User, fallback: object = None) -> str:
    return str(user.username or fallback or f"user{user.id}")


def _payment_log_username(payment: LavaPayment) -> str | None:
    return f"user{payment.user_id}" if payment.user_id else None


def _webhook_log_fields(payment: LavaPayment, *, contract_id: str, event_type: str, status_value: str, **extra: object) -> dict[str, object]:
    return {
        "contract_id": contract_id,
        "lava_event": event_type,
        "status": status_value,
        "amount": payment.amount,
        "currency": payment.currency,
        "product_id": payment.product_id,
        "product_title": payment.product_title,
        **extra,
    }


def _flatten_text(value: object) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())

    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)

    return str(value)


def _lava_error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = None

    if isinstance(data, dict):
        return _flatten_text(
            [
                data.get("error"),
                data.get("message"),
                data.get("description"),
                data.get("details"),
            ]
        ).strip()

    return response.text[:1000]


def _lava_invoice_error_detail(response: httpx.Response, *, has_promo_code: bool) -> str:
    text = _lava_error_text(response)
    normalized = text.lower()

    if has_promo_code:
        if LAVA_PROMO_USAGE_LIMIT_RE.search(text):
            return "lava_promo_code_usage_limit_exceeded"

        if LAVA_PROMO_REJECTION_RE.search(text):
            return "lava_promo_code_rejected"

    if response.status_code in {401, 403}:
        return "lava_api_unauthorized"

    if response.status_code == 404 or "offer" in normalized and "not found" in normalized:
        return "lava_offer_not_found"

    if response.status_code == 429:
        return "lava_rate_limited"

    if response.status_code in {400, 422}:
        if "email" in normalized:
            return "lava_email_rejected"

        if "currency" in normalized:
            return "lava_currency_rejected"

        if "payment" in normalized and ("method" in normalized or "provider" in normalized):
            return "lava_payment_method_rejected"

        return "lava_request_rejected"

    if response.status_code >= 500:
        return "lava_service_unavailable"

    return "lava_invoice_failed"


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))

    except (InvalidOperation, ValueError, TypeError):
        return None


def _is_zero_amount(value: Decimal | None) -> bool:
    return value is not None and value == Decimal("0")


def _payload_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _extract_contract_id(payload: dict[str, Any]) -> str:
    return _clean(payload.get("contractId") or payload.get("id"), max_len=128)


def _extract_event_type(payload: dict[str, Any]) -> str:
    return _clean(payload.get("eventType"), max_len=128)


def _extract_buyer_email(payload: dict[str, Any]) -> str:
    buyer = _payload_dict(payload, "buyer")
    return _clean(buyer.get("email"), max_len=254)


def _extract_product(payload: dict[str, Any]) -> dict[str, Any]:
    return _payload_dict(payload, "product")


def _extract_product_id(payload: dict[str, Any]) -> str:
    product = _extract_product(payload)
    return _clean(product.get("id"), max_len=128)


def _extract_product_title(payload: dict[str, Any]) -> str:
    product = _extract_product(payload)
    return _clean(product.get("title"), max_len=256)


def _extract_amount_and_currency(payload: dict[str, Any]) -> tuple[Decimal | None, str]:
    amount_total = payload.get("amountTotal")
    if isinstance(amount_total, dict):
        amount_value = amount_total.get("amount")
        if amount_value is None:
            amount_value = amount_total.get("value")
        amount = _decimal_or_none(amount_value)
        currency = _clean(amount_total.get("currency"), max_len=3).upper()
        if amount is not None:
            return amount, currency or LAVA_CURRENCY

    amount = _decimal_or_none(payload.get("amount"))
    currency = _clean(payload.get("currency"), max_len=3).upper()
    return amount, currency or LAVA_CURRENCY


def _normalized_event(value: str) -> str:
    return _clean(value, max_len=128).lower()


def _is_ignored_lava_event(event_type: str) -> bool:
    return _normalized_event(event_type) in LAVA_IGNORED_EVENTS


def _is_lava_payment_failure(event_type: str, status_value: str) -> bool:
    return (
        _normalized_event(event_type) == LAVA_PAYMENT_FAILED_EVENT
        or _normalize_status(status_value) in LAVA_PAYMENT_FAILED_STATUSES
    )


def _is_lava_payment_success(event_type: str, status_value: str) -> bool:
    return _normalized_event(event_type) == LAVA_PAYMENT_SUCCESS_EVENT


def _configured_product_url() -> str:
    product_url = _clean(settings.LAVA_PRODUCT_URL)
    if not product_url:
        raise HTTPException(status_code=503, detail="lava_product_missing")

    return product_url


def _configured_lava_api_key() -> str:
    api_key = _clean(settings.LAVA_API_KEY)
    if not api_key:
        raise HTTPException(status_code=503, detail="lava_api_key_missing")

    return api_key


def _normalize_plan(value: object) -> str:
    plan = _clean(value).lower()
    if plan in {"year", "annual", "annually", "12", "12m"}:
        return LAVA_YEAR_PLAN

    if plan in {"", "month", "monthly", "1", "1m"}:
        return LAVA_MONTH_PLAN

    raise HTTPException(status_code=422, detail="lava_plan_invalid")


def _configured_offer_for_plan(plan: str) -> tuple[str, int]:
    if plan == LAVA_YEAR_PLAN:
        offer_id = _clean(settings.LAVA_YEARLY_OFFER_ID)
        if not offer_id:
            raise HTTPException(status_code=503, detail="lava_yearly_offer_missing")

        return offer_id, LAVA_MONTHS_BY_PLAN[LAVA_YEAR_PLAN]

    offer_id = _clean(settings.LAVA_MONTHLY_OFFER_ID)
    if not offer_id:
        raise HTTPException(status_code=503, detail="lava_monthly_offer_missing")

    return offer_id, LAVA_MONTHS_BY_PLAN[LAVA_MONTH_PLAN]


def _normalize_buyer_email(value: object) -> str:
    email = _clean(value, max_len=254).lower()
    if not email:
        raise HTTPException(status_code=422, detail="lava_email_required")

    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="lava_email_invalid")

    return email


def _normalize_lava_currency(value: object) -> str:
    currency = _clean(value, max_len=3).upper() or LAVA_CURRENCY
    if currency not in LAVA_CURRENCIES:
        raise HTTPException(status_code=422, detail="lava_currency_invalid")

    return currency


def _normalize_payment_provider(value: object) -> str:
    provider = _clean(value, max_len=32).upper()
    if provider and provider not in LAVA_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=422, detail="lava_payment_provider_invalid")

    return provider


def _normalize_payment_method(value: object) -> str:
    method = _clean(value, max_len=32).upper()
    if method and method not in LAVA_PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="lava_payment_method_invalid")

    return method


def _normalize_promo_code(value: object) -> str:
    promo_code = _clean(value, max_len=36)
    if promo_code and not PROMO_CODE_RE.match(promo_code):
        raise HTTPException(status_code=422, detail="lava_promo_code_invalid")

    return promo_code


def _ensure_payment_method_supported(*, currency: str, payment_provider: str, payment_method: str) -> None:
    if not payment_provider or not payment_method:
        raise HTTPException(status_code=422, detail="lava_payment_method_required")

    allowed: set[tuple[str, str, str]] = {
        ("RUB", "SMART_GLOCAL", "CARD"),
        ("RUB", "PAY2ME", "SBP"),
    }
    if (currency, payment_provider, payment_method) not in allowed:
        raise HTTPException(status_code=422, detail="lava_payment_method_unsupported")


def _normalize_invoice_options(payload: LavaPaymentLinkCreateIn | None) -> tuple[str, str, str, str]:
    currency = _normalize_lava_currency(payload.currency if payload is not None else None)
    promo_code = _normalize_promo_code(payload.promo_code if payload is not None else None)
    if currency != LAVA_CURRENCY:
        return currency, "", "", promo_code

    payment_provider = _normalize_payment_provider(
        payload.payment_provider if payload is not None else None
    )
    payment_method = _normalize_payment_method(
        payload.payment_method if payload is not None else None
    )
    _ensure_payment_method_supported(
        currency=currency,
        payment_provider=payment_provider,
        payment_method=payment_method,
    )
    return currency, payment_provider, payment_method, promo_code


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


def _invoice_client_utm(*, token: str, user_id: int) -> dict[str, str]:
    return {
        "utm_source": "mafia_site",
        "utm_medium": "subscription",
        "utm_campaign": "lava_subscription",
        "utm_term": str(user_id),
        "utm_content": token,
    }


def _invoice_request_payload(*, email: str, offer_id: str, currency: str, payment_provider: str, payment_method: str, promo_code: str, token: str, user_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "offerId": offer_id,
        "currency": currency,
        "buyerLanguage": LAVA_BUYER_LANGUAGE,
        "clientUtm": _invoice_client_utm(token=token, user_id=user_id),
    }
    if payment_provider:
        payload["paymentProvider"] = payment_provider

    if payment_method:
        payload["paymentMethod"] = payment_method

    if promo_code:
        payload["promoCode"] = promo_code

    return payload


def _lava_invoice_url() -> str:
    return f"{LAVA_API_BASE_URL}{LAVA_INVOICE_PATH}"


async def _create_lava_invoice(payload: dict[str, Any]) -> dict[str, Any]:
    url = _lava_invoice_url()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Api-Key": _configured_lava_api_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=LAVA_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        log.warning("lava.invoice.timeout", url=url)
        raise HTTPException(status_code=504, detail="lava_invoice_timeout") from exc

    except httpx.HTTPError as exc:
        log.warning("lava.invoice.request_failed", url=url, error=type(exc).__name__)
        raise HTTPException(status_code=502, detail="lava_invoice_request_failed") from exc

    if response.status_code < 200 or response.status_code >= 300:
        body = _lava_error_text(response)[:1000]
        detail = _lava_invoice_error_detail(
            response,
            has_promo_code=bool(payload.get("promoCode")),
        )
        log.warning(
            "lava.invoice.bad_status",
            status_code=response.status_code,
            body=body,
            detail=detail,
        )
        status_code = 422 if detail.startswith("lava_promo_") or detail.endswith("_rejected") else 502
        if detail in {"lava_api_unauthorized", "lava_offer_not_found"}:
            status_code = 503
        elif detail == "lava_rate_limited":
            status_code = 429
        elif detail == "lava_service_unavailable":
            status_code = 503

        raise HTTPException(status_code=status_code, detail=detail)

    try:
        data = response.json()
    except ValueError as exc:
        log.warning("lava.invoice.invalid_json", body=response.text[:1000])
        raise HTTPException(status_code=502, detail="lava_invoice_invalid_response") from exc

    if not isinstance(data, dict):
        log.warning("lava.invoice.invalid_payload", payload_type=type(data).__name__)
        raise HTTPException(status_code=502, detail="lava_invoice_invalid_response")

    return data


def _extract_utm_value(payload: dict[str, Any], key: str) -> str:
    return _clean(_payload_dict(payload, "clientUtm").get(key))


def _extract_tracking_token(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("metadataToken"),
        payload.get("trackingToken"),
        _extract_utm_value(payload, "utm_content"),
        _extract_utm_value(payload, "utm_id"),
    ]
    for candidate in candidates:
        token = _clean(candidate)
        if TRACKING_TOKEN_RE.match(token):
            return token

    return ""


def _positive_int_or_none(value: object) -> int | None:
    try:
        number = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None

    return number if number > 0 else None


def _extract_tracking_user_id(payload: dict[str, Any]) -> int | None:
    candidates = [
        payload.get("metadataUserId"),
        payload.get("trackingUserId"),
        payload.get("externalUserId"),
        payload.get("clientUserId"),
        payload.get("mafiaUserId"),
        _extract_utm_value(payload, "utm_term"),
    ]
    for candidate in candidates:
        user_id = _positive_int_or_none(candidate)
        if user_id is not None:
            return user_id

    return None


def _expected_webhook_secrets() -> list[str]:
    secret = _clean(settings.LAVA_WEBHOOK_SECRET)
    return [secret] if secret else []


def _bearer_token(authorization: str | None) -> str:
    value = _clean(authorization)
    if value.lower().startswith("bearer "):
        return value[7:].strip()

    return ""


def _basic_credentials(authorization: str | None) -> tuple[str, str] | None:
    value = _clean(authorization)
    if not value.lower().startswith("basic "):
        return None

    try:
        decoded = base64.b64decode(value[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None

    username, sep, password = decoded.partition(":")
    if not sep:
        return None

    return username, password


def _provided_basic_secrets(authorization: str | None) -> list[str]:
    credentials = _basic_credentials(authorization)
    if credentials is None:
        return []

    username, password = credentials
    return [f"{username}:{password}", password]


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
            *_provided_basic_secrets(authorization),
        )
        if value
    ]


def _ensure_webhook_authorized(request: Request, *, x_api_key: str | None, x_webhook_secret: str | None, authorization: str | None) -> None:
    expected_values = _expected_webhook_secrets()
    if not expected_values:
        raise HTTPException(status_code=503, detail="lava_webhook_secret_missing")

    provided_values = _provided_webhook_secrets(
        request,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )
    if not any(
        compare_digest(provided, expected)
        for provided in provided_values
        for expected in expected_values
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


async def _find_or_create_payment_for_webhook(session: AsyncSession, *, contract_id: str, token: str, user_id: int | None, payload: dict[str, Any]) -> LavaPayment:
    payment = await _find_payment_by_contract(session, contract_id)
    if payment is not None:
        payment.metadata_token = payment.metadata_token or token or None
        payment.user_id = payment.user_id or user_id
        return payment

    payment = LavaPayment(
        contract_id=contract_id,
        user_id=user_id,
        metadata_token=token or None,
        status="webhook_received",
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

    was_new_subscription = subscription is None
    had_active_subscription = bool(
        subscription is not None and subscription.starts_at <= now < subscription.ends_at
    )
    grant_kind = "new" if was_new_subscription else "extended" if had_active_subscription else "renewed"
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
        from .global_chat import emit_global_chat_profile_theme_sync

        await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        await notify_subscription_upsert(
            session,
            user,
            subscription,
            extended=had_active_subscription,
        )

    await _log_lava_event(
        session,
        event="subscription_granted",
        user_id=uid,
        username=str(user.username or f"user{uid}"),
        contract_id=payment.contract_id,
        grant=grant_kind,
        plan=payment.plan,
        months=months,
        offer_id=payment.offer_id,
        amount=payment.amount,
        currency=payment.currency,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
    )
    return True
