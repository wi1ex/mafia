from __future__ import annotations
import asyncio
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
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.logging import log_action
from ..core.settings import settings
from ..models.kassa_payment import KassaPayment
from ..models.subscription import UserSubscription
from ..models.user import User
from ..schemas.payments import KassaPaymentLinkCreateIn, KassaPaymentLinkCreateOut
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
from .user_cache import get_user_profile_cached, refresh_user_profile_cache
from ..api.utils import (
    emit_auth_profile_sync,
    emit_room_profile_theme_sync,
    format_subscription_purchase_duration,
    notify_subscription_upsert,
)
from .telegram import send_text_message

log = structlog.get_logger()

KASSA_CURRENCY = "RUB"
KASSA_API_BASE_URL = "https://gate.lava.top"
KASSA_INVOICE_PATH = "/api/v3/invoice"
KASSA_BUYER_LANGUAGE = "RU"
KASSA_REQUEST_TIMEOUT_SECONDS = 15
KASSA_CURRENCIES = {"RUB", "USD", "EUR"}
KASSA_PAYMENT_PROVIDERS = {"SMART_GLOCAL", "PAY2ME"}
KASSA_PAYMENT_METHODS = {"CARD", "SBP"}
KASSA_MONTH_PLAN = "month"
KASSA_YEAR_PLAN = "year"
KASSA_MONTHS_BY_PLAN = {
    KASSA_MONTH_PLAN: 1,
    KASSA_YEAR_PLAN: 12,
}
KASSA_TRACKING_TOKEN_PREFIX = "kassa_"
TRACKING_TOKEN_RE = re.compile(r"^kassa_[A-Za-z0-9_-]{24,90}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
PROMO_CODE_RE = re.compile(r"^[A-Z0-9_-]{3,36}$")
KASSA_PROMO_REJECTION_RE = re.compile(r"promo|promocode|coupon|discount|промо|скид", re.I)
KASSA_PROMO_USAGE_LIMIT_RE = re.compile(r"usage\s+limit|limit.*exceed|лимит|исчерпан", re.I)
KASSA_PAYMENT_SUCCESS_EVENT = "payment.success"
KASSA_PAYMENT_FAILED_EVENT = "payment.failed"
KASSA_PAYMENT_FAILED_STATUSES = {"failed", "cancelled", "refunded", "chargeback"}
KASSA_IGNORED_EVENTS = {
    "subscription.recurring.payment.success",
    "subscription.recurring.payment.failed",
    "subscription.cancelled",
}
KASSA_LOG_ACTION = "kassa_payment"
KASSA_SUBSCRIPTION_ADMIN_TELEGRAM_ID = int(settings.ADMIN_TELEGRAM_ID)


def _clean(value: object, *, max_len: int | None = None) -> str:
    text = str(value or "").strip()
    if max_len is not None:
        return text[:max_len]

    return text


def _is_safe_kassa_payment_url(value: str) -> bool:
    if not value or len(value) > 2048 or any(char.isspace() for char in value):
        return False

    try:
        parsed = urlsplit(value)
    except ValueError:
        return False

    return bool(
        parsed.scheme.lower() == "https"
        and parsed.hostname
        and parsed.username is None
        and parsed.password is None
    )


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


KASSA_LOG_FIELD_ORDER = (
    "event",
    "email",
    "plan",
    "currency",
    "payment_method",
    "promo_code",
    "reason",
    "amount",
    "result",
    "status",
)
KASSA_LOG_FIELD_LABELS = {
    "event": "Событие",
    "email": "Email",
    "plan": "Тариф",
    "currency": "Валюта",
    "payment_method": "Способ оплаты",
    "promo_code": "Промокод",
    "reason": "Причина",
    "amount": "Сумма",
    "result": "Результат",
    "status": "Статус",
}
KASSA_LOG_EVENT_LABELS = {
    "payment_link": "выдача ссылки на оплату",
    "payment_result": "результат оплаты",
}
KASSA_LOG_PLAN_LABELS = {
    KASSA_MONTH_PLAN: "1 месяц",
    KASSA_YEAR_PLAN: "12 месяцев",
}
KASSA_LOG_PAYMENT_METHOD_LABELS = {
    "CARD": "карта",
    "SBP": "СБП",
}
KASSA_LOG_REASON_LABELS = {
    "kassa_invoice_timeout": "сервис не ответил вовремя",
    "kassa_invoice_request_failed": "не удалось подключиться к сервису",
    "kassa_api_unauthorized": "API-ключ сервиса не принят",
    "kassa_offer_not_found": "тариф сервиса не найден",
    "kassa_rate_limited": "сервис ограничил частоту запросов",
    "kassa_email_rejected": "сервис не принял email",
    "kassa_currency_rejected": "сервис не принял валюту",
    "kassa_payment_method_rejected": "сервис не принял способ оплаты",
    "kassa_request_rejected": "сервис отклонил параметры платежа",
    "kassa_service_unavailable": "сервис временно недоступен",
    "kassa_invoice_invalid_response": "сервис вернул некорректный ответ",
    "kassa_contract_id_missing": "сервис не вернул номер договора",
    "kassa_payment_url_missing": "сервис не вернул ссылку на оплату",
    "kassa_payment_url_invalid": "сервис вернул небезопасную ссылку на оплату",
    "kassa_subscription_grant_failed": "оплата подтверждена, но подписка не выдана",
    "kassa_free_invoice_not_processed": (
        "нулевой счет создан, но подписка не активировалась"
    ),
    "kassa_plan_invalid": "выбран неподдерживаемый тариф",
    "kassa_yearly_offer_missing": "не настроен годовой тариф сервиса",
    "kassa_monthly_offer_missing": "не настроен месячный тариф сервиса",
    "kassa_email_required": "email не указан",
    "kassa_email_invalid": "email некорректен",
    "kassa_currency_invalid": "выбрана неподдерживаемая валюта",
    "kassa_payment_provider_invalid": (
        "выбран неподдерживаемый платежный провайдер"
    ),
    "kassa_payment_method_invalid": (
        "выбран неподдерживаемый способ оплаты"
    ),
    "kassa_promo_code_invalid": "промокод некорректен",
    "kassa_promo_code_usage_limit_exceeded": (
        "лимит использования промокода исчерпан"
    ),
    "kassa_promo_code_rejected": "сервис не принял промокод",
    "kassa_payment_method_required": "способ оплаты не выбран",
    "kassa_payment_method_unsupported": (
        "способ оплаты недоступен для выбранной валюты"
    ),
    "free_invoice_not_processed": (
        "нулевой счет создан, но подписка не активировалась"
    ),
    "user_or_subscription_period_missing": (
        "не найден пользователь или период подписки"
    ),
    "product_mismatch": (
        "продукт в уведомлении сервиса не совпал с настройками"
    ),
    "payment_failed": "платеж не прошел",
    "unhandled_webhook": "уведомление сервиса не обработано",
}
KASSA_LOG_RESULT_LABELS = {
    "payment_url_created": "ссылка на оплату выдана",
    "payment_link_failed": "ошибка выдачи ссылки на оплату",
    "subscription_granted_without_payment_url": (
        "продукт сразу оплачен, подписка выдана"
    ),
    "subscription_granted": "платеж прошел, подписка выдана",
    "subscription_not_granted": (
        "платеж прошел, но подписка не выдана"
    ),
    "payment_failed": "платеж не прошел",
    "product_mismatch": (
        "платеж не засчитан из-за другого продукта"
    ),
    "unhandled_webhook": "результат платежа не обработан",
}
KASSA_LOG_STATUS_LABELS = {
    "success": "успешно",
    "failed": "ошибка",
    "pending": "ожидает оплаты",
    "paid": "оплачен",
    "processed": "обработан",
    "not_granted": "подписка не выдана",
    "product_mismatch": "другой продукт",
    "unhandled": "не обработан",
    "cancelled": "отменен",
    "refunded": "возврат",
    "chargeback": "чарджбек",
}


def _localized_kassa_log_value(field: str, value: object) -> str:
    raw = _log_value(value)
    if raw == "-":
        return raw

    if field == "event":
        return KASSA_LOG_EVENT_LABELS.get(raw, raw)

    if field == "plan":
        return KASSA_LOG_PLAN_LABELS.get(raw, raw)

    if field == "payment_method":
        return KASSA_LOG_PAYMENT_METHOD_LABELS.get(raw.upper(), raw)

    if field == "reason":
        return KASSA_LOG_REASON_LABELS.get(raw, raw)

    if field == "result":
        return KASSA_LOG_RESULT_LABELS.get(raw, raw)

    if field == "status":
        return KASSA_LOG_STATUS_LABELS.get(raw.lower(), raw)

    return raw


def _log_details(event: str, **fields: object) -> str:
    allowed_fields = {"event": event}
    allowed_fields.update(
        {key: value for key, value in fields.items() if key in KASSA_LOG_FIELD_ORDER}
    )
    parts = []
    for key in KASSA_LOG_FIELD_ORDER:
        if key not in allowed_fields:
            continue

        label = KASSA_LOG_FIELD_LABELS[key]
        value = _localized_kassa_log_value(key, allowed_fields[key])
        parts.append(f"{label}: {value}")

    return "; ".join(parts)


async def _log_kassa_event(session: AsyncSession, *, event: str, user_id: int | None, username: str | None, commit: bool = True, **fields: object) -> None:
    await log_action(
        session,
        user_id=user_id,
        username=username,
        action=KASSA_LOG_ACTION,
        details=_log_details(event, **fields),
        commit=commit,
    )


def _user_log_username(user: User, fallback: object = None) -> str:
    return str(user.username or fallback or f"user{user.id}")


async def _payment_log_username(session: AsyncSession, payment: KassaPayment) -> str | None:
    user_id = int(payment.user_id or 0)
    if user_id <= 0:
        return None

    profile = await get_user_profile_cached(session, user_id)
    username = str((profile or {}).get("username") or "").strip()
    return username or f"user{user_id}"


def _kassa_payment_amount_text(payment: KassaPayment) -> str:
    if payment.amount is None:
        return "-"

    currency = _clean(payment.currency, max_len=3).upper()
    amount = str(payment.amount)
    return f"{amount} {currency}" if currency else amount


async def _send_kassa_subscription_admin_telegram_message(*, uid: int, chat_id: int, text: str) -> None:
    try:
        send_result = await send_text_message(
            chat_id=chat_id,
            text=text,
        )
    except Exception:
        log.warning(
            "kassa.subscription.admin_telegram_notify_failed",
            uid=uid,
            reason="unexpected_error",
            exc_info=True,
        )
        return

    if not send_result.ok:
        log.warning(
            "kassa.subscription.admin_telegram_notify_failed",
            uid=uid,
            reason=send_result.reason,
        )


def _schedule_kassa_subscription_admin_telegram_message(*, uid: int, chat_id: int, text: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.warning(
            "kassa.subscription.admin_telegram_notify_failed",
            uid=uid,
            reason="event_loop_unavailable",
        )
        return

    loop.create_task(_send_kassa_subscription_admin_telegram_message(uid=uid, chat_id=chat_id, text=text))


async def _send_kassa_subscription_admin_notice(
    *,
    user: User,
    payment: KassaPayment,
    months: int,
) -> None:
    uid = int(user.id)
    username = str(user.username or f"user{uid}")
    duration = format_subscription_purchase_duration(months=months)
    amount = _kassa_payment_amount_text(payment)
    text = (
        "Покупка подписки\n"
        f"Пользователь: {username}\n"
        f"ID: {uid}\n"
        f"Срок: {duration}\n"
        f"Сумма: {amount}"
    )
    _schedule_kassa_subscription_admin_telegram_message(
        uid=uid,
        chat_id=KASSA_SUBSCRIPTION_ADMIN_TELEGRAM_ID,
        text=text,
    )


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


def _kassa_error_text(response: httpx.Response) -> str:
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


def _kassa_invoice_error_detail(response: httpx.Response, *, has_promo_code: bool) -> str:
    text = _kassa_error_text(response)
    normalized = text.lower()

    if has_promo_code:
        if KASSA_PROMO_USAGE_LIMIT_RE.search(text):
            return "kassa_promo_code_usage_limit_exceeded"

        if KASSA_PROMO_REJECTION_RE.search(text):
            return "kassa_promo_code_rejected"

    if response.status_code in {401, 403}:
        return "kassa_api_unauthorized"

    if response.status_code == 404 or "offer" in normalized and "not found" in normalized:
        return "kassa_offer_not_found"

    if response.status_code == 429:
        return "kassa_rate_limited"

    if response.status_code in {400, 422}:
        if "email" in normalized:
            return "kassa_email_rejected"

        if "currency" in normalized:
            return "kassa_currency_rejected"

        if "payment" in normalized and ("method" in normalized or "provider" in normalized):
            return "kassa_payment_method_rejected"

        return "kassa_request_rejected"

    if response.status_code >= 500:
        return "kassa_service_unavailable"

    return "kassa_invoice_failed"


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
            return amount, currency or KASSA_CURRENCY

    amount = _decimal_or_none(payload.get("amount"))
    currency = _clean(payload.get("currency"), max_len=3).upper()
    return amount, currency or KASSA_CURRENCY


def _extract_payment_method_from_payload(payload: dict[str, Any]) -> str:
    payment = _payload_dict(payload, "payment")
    candidates = [
        payload.get("paymentMethod"),
        payload.get("payment_method"),
        payment.get("paymentMethod"),
        payment.get("payment_method"),
        payment.get("method"),
    ]
    for candidate in candidates:
        method = _clean(candidate, max_len=32).upper()
        if method:
            return method

    return ""


def _extract_payment_method_for_log(payment: KassaPayment, webhook_payload: dict[str, Any]) -> str:
    method = _extract_payment_method_from_payload(webhook_payload)
    if method:
        return method

    try:
        stored_payload = json.loads(payment.raw_payload or "{}")
    except (TypeError, ValueError):
        stored_payload = {}

    if not isinstance(stored_payload, dict):
        return ""

    request_payload = stored_payload.get("request")
    if isinstance(request_payload, dict):
        method = _clean(request_payload.get("paymentMethod"), max_len=32).upper()
        if method:
            return method

    return _extract_payment_method_from_payload(stored_payload)


def _normalized_event(value: str) -> str:
    return _clean(value, max_len=128).lower()


def _is_ignored_kassa_event(event_type: str) -> bool:
    return _normalized_event(event_type) in KASSA_IGNORED_EVENTS


def _is_kassa_payment_failure(event_type: str, status_value: str) -> bool:
    return (
        _normalized_event(event_type) == KASSA_PAYMENT_FAILED_EVENT
        or _normalize_status(status_value) in KASSA_PAYMENT_FAILED_STATUSES
    )


def _is_kassa_payment_success(event_type: str, status_value: str) -> bool:
    return _normalized_event(event_type) == KASSA_PAYMENT_SUCCESS_EVENT


def _is_terminal_kassa_rejection(event_type: str, status_value: str) -> bool:
    return (
        _is_kassa_payment_failure(event_type, status_value)
        or _normalize_status(status_value) == "product-mismatch"
    )


def _configured_product_url() -> str:
    product_url = _clean(settings.KASSA_PRODUCT_URL)
    if not product_url:
        raise HTTPException(status_code=503, detail="kassa_product_missing")

    return product_url


def _configured_kassa_api_key() -> str:
    api_key = _clean(settings.KASSA_API_KEY)
    if not api_key:
        raise HTTPException(status_code=503, detail="kassa_api_key_missing")

    return api_key


def _normalize_plan(value: object) -> str:
    plan = _clean(value).lower()
    if plan in {"year", "annual", "annually", "12", "12m"}:
        return KASSA_YEAR_PLAN

    if plan in {"", "month", "monthly", "1", "1m"}:
        return KASSA_MONTH_PLAN

    raise HTTPException(status_code=422, detail="kassa_plan_invalid")


def _configured_offer_for_plan(plan: str) -> tuple[str, int]:
    if plan == KASSA_YEAR_PLAN:
        offer_id = _clean(settings.KASSA_YEARLY_OFFER_ID)
        if not offer_id:
            raise HTTPException(status_code=503, detail="kassa_yearly_offer_missing")

        return offer_id, KASSA_MONTHS_BY_PLAN[KASSA_YEAR_PLAN]

    offer_id = _clean(settings.KASSA_MONTHLY_OFFER_ID)
    if not offer_id:
        raise HTTPException(status_code=503, detail="kassa_monthly_offer_missing")

    return offer_id, KASSA_MONTHS_BY_PLAN[KASSA_MONTH_PLAN]


def _normalize_buyer_email(value: object) -> str:
    email = _clean(value, max_len=254).lower()
    if not email:
        raise HTTPException(status_code=422, detail="kassa_email_required")

    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="kassa_email_invalid")

    return email


def _normalize_kassa_currency(value: object) -> str:
    currency = _clean(value, max_len=3).upper() or KASSA_CURRENCY
    if currency not in KASSA_CURRENCIES:
        raise HTTPException(status_code=422, detail="kassa_currency_invalid")

    return currency


def _normalize_payment_provider(value: object) -> str:
    provider = _clean(value, max_len=32).upper()
    if provider and provider not in KASSA_PAYMENT_PROVIDERS:
        raise HTTPException(status_code=422, detail="kassa_payment_provider_invalid")

    return provider


def _normalize_payment_method(value: object) -> str:
    method = _clean(value, max_len=32).upper()
    if method and method not in KASSA_PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="kassa_payment_method_invalid")

    return method


def _normalize_promo_code(value: object) -> str:
    promo_code = _clean(value, max_len=36)
    if promo_code and not PROMO_CODE_RE.match(promo_code):
        raise HTTPException(status_code=422, detail="kassa_promo_code_invalid")

    return promo_code


def _ensure_payment_method_supported(*, currency: str, payment_provider: str, payment_method: str) -> None:
    if not payment_provider or not payment_method:
        raise HTTPException(status_code=422, detail="kassa_payment_method_required")

    allowed: set[tuple[str, str, str]] = {
        ("RUB", "SMART_GLOCAL", "CARD"),
        ("RUB", "PAY2ME", "SBP"),
    }
    if (currency, payment_provider, payment_method) not in allowed:
        raise HTTPException(status_code=422, detail="kassa_payment_method_unsupported")


def _normalize_invoice_options(payload: KassaPaymentLinkCreateIn | None) -> tuple[str, str, str, str]:
    currency = _normalize_kassa_currency(payload.currency if payload is not None else None)
    promo_code = _normalize_promo_code(payload.promo_code if payload is not None else None)
    if currency != KASSA_CURRENCY:
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
    return f"{KASSA_TRACKING_TOKEN_PREFIX}{token_urlsafe(24)}"


def _invoice_client_utm(*, token: str, user_id: int) -> dict[str, str]:
    return {
        "utm_source": "mafia_site",
        "utm_medium": "subscription",
        "utm_campaign": "kassa_subscription",
        "utm_term": str(user_id),
        "utm_content": token,
    }


def _invoice_request_payload(*, email: str, offer_id: str, currency: str, payment_provider: str, payment_method: str, promo_code: str, token: str, user_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "offerId": offer_id,
        "currency": currency,
        "buyerLanguage": KASSA_BUYER_LANGUAGE,
        "clientUtm": _invoice_client_utm(token=token, user_id=user_id),
    }
    if payment_provider:
        payload["paymentProvider"] = payment_provider

    if payment_method:
        payload["paymentMethod"] = payment_method

    if promo_code:
        payload["promoCode"] = promo_code

    return payload


def _kassa_invoice_url() -> str:
    return f"{KASSA_API_BASE_URL}{KASSA_INVOICE_PATH}"


async def _create_kassa_invoice(payload: dict[str, Any]) -> dict[str, Any]:
    url = _kassa_invoice_url()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Api-Key": _configured_kassa_api_key(),
    }
    try:
        async with httpx.AsyncClient(timeout=KASSA_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        log.warning("kassa.invoice.timeout", url=url)
        raise HTTPException(status_code=504, detail="kassa_invoice_timeout") from exc

    except httpx.HTTPError as exc:
        log.warning("kassa.invoice.request_failed", url=url, error=type(exc).__name__)
        raise HTTPException(status_code=502, detail="kassa_invoice_request_failed") from exc

    if response.status_code < 200 or response.status_code >= 300:
        body = _kassa_error_text(response)[:1000]
        detail = _kassa_invoice_error_detail(
            response,
            has_promo_code=bool(payload.get("promoCode")),
        )
        log.warning(
            "kassa.invoice.bad_status",
            status_code=response.status_code,
            body=body,
            detail=detail,
        )
        status_code = 422 if detail.startswith("kassa_promo_") or detail.endswith("_rejected") else 502
        if detail in {"kassa_api_unauthorized", "kassa_offer_not_found"}:
            status_code = 503
        elif detail == "kassa_rate_limited":
            status_code = 429
        elif detail == "kassa_service_unavailable":
            status_code = 503

        raise HTTPException(status_code=status_code, detail=detail)

    try:
        data = response.json()
    except ValueError as exc:
        log.warning("kassa.invoice.invalid_json", body=response.text[:1000])
        raise HTTPException(status_code=502, detail="kassa_invoice_invalid_response") from exc

    if not isinstance(data, dict):
        log.warning("kassa.invoice.invalid_payload", payload_type=type(data).__name__)
        raise HTTPException(status_code=502, detail="kassa_invoice_invalid_response")

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
    secret = _clean(settings.KASSA_WEBHOOK_SECRET)
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
        raise HTTPException(status_code=503, detail="kassa_webhook_secret_missing")

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
            "kassa.webhook.unauthorized",
            client=str(request.client.host if request.client else ""),
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


def _product_matches_expected(product_id: str) -> bool:
    expected = _configured_product_id()
    return not expected or not product_id or product_id == expected


async def _lock_payment_contract(session: AsyncSession, contract_id: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:contract_id, 0))"),
        {"contract_id": contract_id},
    )


async def _upsert_and_lock_payment(
    session: AsyncSession,
    *,
    contract_id: str,
    user_id: int | None,
    metadata_token: str,
    status: str,
    raw_payload: str,
) -> KassaPayment:
    statement = (
        pg_insert(KassaPayment)
        .values(
            contract_id=contract_id,
            user_id=user_id,
            metadata_token=metadata_token or None,
            status=status,
            subscription_months=0,
            raw_payload=raw_payload,
        )
        .on_conflict_do_nothing(index_elements=[KassaPayment.contract_id])
    )
    await session.execute(statement)
    payment = await session.scalar(
        select(KassaPayment)
        .where(KassaPayment.contract_id == contract_id)
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment is None:
        raise RuntimeError("kassa payment upsert did not return a contract row")

    return payment


async def _grant_subscription_for_payment(session: AsyncSession, payment: KassaPayment) -> bool:
    uid = int(payment.user_id or 0)
    months = int(payment.subscription_months or 0)
    if uid <= 0 or months <= 0:
        return False

    user = await session.scalar(
        select(User)
        .where(User.id == uid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user or user.deleted_at is not None:
        return False

    now = datetime.now(timezone.utc)
    subscription = await session.scalar(
        select(UserSubscription)
        .where(UserSubscription.user_id == uid)
        .limit(1)
        .with_for_update()
        .execution_options(populate_existing=True)
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
        from .global_chat import emit_global_chat_profile_theme_sync

        await emit_global_chat_profile_theme_sync(uid, theme_state.color, theme_state.icon)
    with suppress(Exception):
        await notify_subscription_upsert(
            session,
            user,
            subscription,
            extended=had_active_subscription,
            months=months,
        )
    with suppress(Exception):
        await _send_kassa_subscription_admin_notice(
            user=user,
            payment=payment,
            months=months,
        )

    return True


async def create_kassa_payment_link(
    session: AsyncSession,
    *,
    payload: KassaPaymentLinkCreateIn | None,
    user_id: int,
    username: object = None,
) -> KassaPaymentLinkCreateOut:
    uid = int(user_id)
    user = await session.get(User, uid)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="user_not_found")

    log_username = _user_log_username(user, username)
    raw_email = _clean(payload.email if payload is not None else None, max_len=254).lower()
    raw_plan = _clean(payload.plan if payload is not None else None).lower() or KASSA_MONTH_PLAN
    raw_currency = (
        _clean(payload.currency if payload is not None else None, max_len=3).upper()
        or KASSA_CURRENCY
    )
    raw_payment_method = _clean(
        payload.payment_method if payload is not None else None,
        max_len=32,
    ).upper()
    raw_promo_code = _clean(payload.promo_code if payload is not None else None, max_len=36)
    try:
        plan = _normalize_plan(payload.plan if payload is not None else None)
        email = _normalize_buyer_email(payload.email if payload is not None else None)
        requested_currency, payment_provider, payment_method, promo_code = (
            _normalize_invoice_options(payload)
        )
        offer_id, months = _configured_offer_for_plan(plan)
    except HTTPException as exc:
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=raw_email,
            plan=raw_plan,
            currency=raw_currency,
            payment_method=raw_payment_method,
            promo_code=raw_promo_code,
            reason=exc.detail,
            result="payment_link_failed",
            status="failed",
        )
        raise

    token = _new_tracking_token()
    invoice_request = _invoice_request_payload(
        email=email,
        offer_id=offer_id,
        currency=requested_currency,
        payment_provider=payment_provider,
        payment_method=payment_method,
        promo_code=promo_code,
        token=token,
        user_id=uid,
    )
    try:
        invoice = await _create_kassa_invoice(invoice_request)
    except HTTPException as exc:
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason=exc.detail,
            result="payment_link_failed",
            status="failed",
        )
        raise

    contract_id = _clean(invoice.get("id"), max_len=128)
    payment_url = _clean(invoice.get("paymentUrl"))
    if not contract_id:
        log.warning(
            "kassa.invoice.contract_id_missing",
            response=_json_dumps(invoice)[:1000],
        )
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason="kassa_contract_id_missing",
            result="payment_link_failed",
            status="failed",
        )
        raise HTTPException(status_code=502, detail="kassa_contract_id_missing")

    amount, invoice_currency = _extract_amount_and_currency(invoice)
    if payment_url and not _is_safe_kassa_payment_url(payment_url):
        log.warning(
            "kassa.invoice.payment_url_invalid",
            contract_id=contract_id,
        )
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason="kassa_payment_url_invalid",
            amount=amount,
            result="payment_link_failed",
            status="failed",
        )
        raise HTTPException(status_code=502, detail="kassa_payment_url_invalid")

    if not payment_url and not _is_zero_amount(amount):
        log.warning(
            "kassa.invoice.payment_url_missing",
            contract_id=contract_id,
            response=_json_dumps(invoice)[:1000],
        )
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason="kassa_payment_url_missing",
            amount=amount,
            result="payment_link_failed",
            status="failed",
        )
        raise HTTPException(status_code=502, detail="kassa_payment_url_missing")

    invoice_record = _json_dumps(
        {
            "kind": "kassa_invoice",
            "request": {**invoice_request, "email": email},
            "response": invoice,
        }
    )
    await _lock_payment_contract(session, contract_id)
    payment = await _upsert_and_lock_payment(
        session,
        contract_id=contract_id,
        user_id=uid,
        metadata_token=token,
        status=_normalize_status(invoice.get("status")) or "invoice_created",
        raw_payload=invoice_record,
    )
    existing_uid = int(payment.user_id or 0)
    existing_token = _clean(payment.metadata_token)
    if (existing_uid and existing_uid != uid) or (
        existing_token and existing_token != token
    ):
        log.error(
            "kassa.invoice.contract_identity_conflict",
            contract_id=contract_id,
            existing_user_id=existing_uid or None,
            requested_user_id=uid,
        )
        raise HTTPException(status_code=502, detail="kassa_invoice_invalid_response")

    stored_event_type = _clean(payment.event_type)
    stored_status = _clean(payment.status)
    early_webhook_rejected = _is_terminal_kassa_rejection(
        stored_event_type,
        stored_status,
    )
    early_webhook_success = (
        not early_webhook_rejected
        and _is_kassa_payment_success(stored_event_type, stored_status)
    )
    payment.user_id = uid
    payment.metadata_token = token
    payment.email = email
    if not payment.event_type and payment.processed_at is None:
        payment.status = _normalize_status(invoice.get("status")) or "invoice_created"
    payment.offer_id = offer_id
    payment.plan = plan
    payment.amount = amount
    payment.currency = invoice_currency or requested_currency
    payment.subscription_months = months
    payment.payment_url = payment_url
    payment.raw_payload = invoice_record
    await session.flush()

    if early_webhook_rejected:
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason=(
                "product_mismatch"
                if _normalize_status(stored_status) == "product-mismatch"
                else "payment_failed"
            ),
            amount=payment.amount,
            result="payment_link_failed",
            status="failed",
            commit=False,
        )
        await session.commit()
        raise HTTPException(status_code=502, detail="kassa_invoice_failed")

    processed = payment.processed_at is not None
    should_grant_now = early_webhook_success or (
        not payment_url and not payment.event_type
    )
    grant_attempted = not processed and should_grant_now
    if grant_attempted:
        processed = await _grant_subscription_for_payment(session, payment)
    else:
        await session.commit()

    if not processed and (grant_attempted or not payment_url):
        failure_reason = (
            "kassa_subscription_grant_failed"
            if early_webhook_success
            else "free_invoice_not_processed"
        )
        await _log_kassa_event(
            session,
            event="payment_link",
            user_id=uid,
            username=log_username,
            email=email,
            plan=plan,
            currency=requested_currency,
            payment_method=payment_method,
            promo_code=promo_code,
            reason=failure_reason,
            amount=payment.amount,
            result="payment_link_failed",
            status="failed",
            commit=False,
        )
        await session.commit()
        raise HTTPException(
            status_code=502,
            detail=(
                "kassa_subscription_grant_failed"
                if early_webhook_success
                else "kassa_free_invoice_not_processed"
            ),
        )

    await _log_kassa_event(
        session,
        event="payment_link",
        user_id=uid,
        username=log_username,
        email=email,
        plan=plan,
        currency=requested_currency,
        payment_method=payment_method,
        promo_code=promo_code,
        amount=payment.amount,
        result=(
            "subscription_granted_without_payment_url"
            if processed
            else "payment_url_created"
        ),
        status="paid" if processed else "success",
    )

    return KassaPaymentLinkCreateOut(
        payment_url="" if processed else payment_url,
        contract_id=contract_id,
        processed=processed,
    )


async def process_kassa_webhook(
    session: AsyncSession,
    *,
    request: Request,
    payload: dict[str, Any],
    x_api_key: str | None,
    x_webhook_secret: str | None,
    authorization: str | None,
) -> None:
    _ensure_webhook_authorized(
        request,
        x_api_key=x_api_key,
        x_webhook_secret=x_webhook_secret,
        authorization=authorization,
    )

    contract_id = _extract_contract_id(payload)
    token = _extract_tracking_token(payload)
    tracking_user_id = _extract_tracking_user_id(payload)
    event_type = _extract_event_type(payload)
    status_value = _normalize_status(payload.get("status"))
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id_missing")

    await _lock_payment_contract(session, contract_id)

    payment = await _upsert_and_lock_payment(
        session,
        contract_id=contract_id,
        user_id=tracking_user_id,
        metadata_token=token,
        status="webhook_received",
        raw_payload=_json_dumps(payload),
    )
    already_processed = payment.processed_at is not None
    payment_method = _extract_payment_method_for_log(payment, payload)
    amount, currency = _extract_amount_and_currency(payload)
    product_id = _extract_product_id(payload)
    product_title = _extract_product_title(payload)

    payment.metadata_token = token or payment.metadata_token
    payment.email = _extract_buyer_email(payload) or payment.email
    if not already_processed:
        payment.event_type = event_type or payment.event_type
        payment.status = status_value or event_type or payment.status
    payment.product_id = product_id or payment.product_id
    payment.product_title = product_title or payment.product_title
    payment.amount = amount if amount is not None else payment.amount
    payment.currency = currency or payment.currency
    payment.raw_payload = _json_dumps(payload)

    if not _product_matches_expected(product_id):
        if not already_processed:
            payment.status = "product_mismatch"
        expected_product_id = _configured_product_id()
        log.warning(
            "kassa.webhook.product_mismatch",
            contract_id=contract_id,
            expected_product_id=expected_product_id,
            actual_product_id=product_id,
        )
        await _log_kassa_event(
            session,
            event="payment_result",
            user_id=payment.user_id,
            username=await _payment_log_username(session, payment),
            email=payment.email,
            plan=payment.plan,
            currency=payment.currency,
            payment_method=payment_method,
            reason="product_mismatch",
            amount=payment.amount,
            result="product_mismatch",
            status="product_mismatch",
            commit=False,
        )
        await session.commit()
        return

    if already_processed:
        await session.commit()
        return

    if _is_ignored_kassa_event(event_type):
        await session.commit()
        return

    if _is_kassa_payment_failure(event_type, status_value):
        await _log_kassa_event(
            session,
            event="payment_result",
            user_id=payment.user_id,
            username=await _payment_log_username(session, payment),
            email=payment.email,
            plan=payment.plan,
            currency=payment.currency,
            payment_method=payment_method,
            reason="payment_failed",
            amount=payment.amount,
            result="payment_failed",
            status=status_value or "failed",
            commit=False,
        )
        await session.commit()
        return

    if _is_kassa_payment_success(event_type, status_value):
        granted = await _grant_subscription_for_payment(session, payment)
        if not granted:
            log.warning(
                "kassa.webhook.grant_skipped",
                contract_id=contract_id,
                user_id=payment.user_id,
                plan=payment.plan,
                months=payment.subscription_months,
                offer_id=payment.offer_id,
                amount=str(payment.amount) if payment.amount is not None else None,
                currency=payment.currency,
            )
            await _log_kassa_event(
                session,
                event="payment_result",
                user_id=payment.user_id,
                username=await _payment_log_username(session, payment),
                email=payment.email,
                plan=payment.plan,
                currency=payment.currency,
                payment_method=payment_method,
                reason="user_or_subscription_period_missing",
                amount=payment.amount,
                result="subscription_not_granted",
                status="not_granted",
                commit=False,
            )
            await session.commit()
        else:
            await _log_kassa_event(
                session,
                event="payment_result",
                user_id=payment.user_id,
                username=await _payment_log_username(session, payment),
                email=payment.email,
                plan=payment.plan,
                currency=payment.currency,
                payment_method=payment_method,
                amount=payment.amount,
                result="subscription_granted",
                status="processed",
            )
        return

    await _log_kassa_event(
        session,
        event="payment_result",
        user_id=payment.user_id,
        username=await _payment_log_username(session, payment),
        email=payment.email,
        plan=payment.plan,
        currency=payment.currency,
        payment_method=payment_method,
        reason="unhandled_webhook",
        amount=payment.amount,
        result="unhandled_webhook",
        status=status_value or "unhandled",
        commit=False,
    )
    await session.commit()
