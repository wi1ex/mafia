from __future__ import annotations
import base64
import hashlib
import json
import re
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from secrets import compare_digest, token_urlsafe
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from uuid import UUID
import httpx
import structlog
from fastapi import HTTPException, Request
from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.settings import settings
from ..models.coin_purchase import CoinPurchase
from ..models.settings import AppSettings
from ..models.user import User
from .coin_prices import DC_CURRENCIES, DC_PACKAGE_QUANTITIES, parse_dc_packages
from .wallet import checked_balance, ensure_purchase_access, get_dc_balance, lock_dc_request, lock_user_balance, notify_coin_operation, persist_coin_operation_notice

log = structlog.get_logger()
API_BASE = "https://gate.lava.top"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
SUCCESS_STATUSES = {"completed", "paid", "success", "successful"}
PENDING_STATUSES = {"created", "new", "in_progress", "pending", "waiting", "waiting_payment", "awaiting_payment", "invoice_created"}
FAILED_STATUSES = {"failed", "cancelled", "canceled", "expired"}
REFUND_EVENTS = {"refund.success", "chargeback.initiated"}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v), ensure_ascii=False))


def decimal_money(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None

    except (InvalidOperation, ValueError, TypeError):
        return None


def event_type(payload: dict) -> str:
    return _clean(payload.get("eventType") or payload.get("event_type")).lower()


def extract_invoice_id(payload: dict) -> str:
    data = _dict(payload.get("data"))
    value = _clean(payload.get("contractId") or payload.get("invoiceId") or data.get("contract_id") or data.get("invoice_id") or (payload.get("id") if not event_type(payload) else None))
    return value if len(value) <= 128 else ""


def extract_money(payload: dict) -> tuple[Decimal | None, str]:
    for row in (payload, _dict(payload.get("data"))):
        total = _dict(row.get("receipt") or row.get("amountTotal"))
        if total:
            return decimal_money(total.get("amount", total.get("value"))), _clean(total.get("currency")).upper()

        if row.get("amount") is not None:
            return decimal_money(row["amount"]), _clean(row.get("currency")).upper()

    return None, ""


def provider_event_key(payload: dict) -> str:
    value = _clean(payload.get("event_id") or payload.get("eventId"))
    if value:
        return value[:160]

    encoded = json.dumps(json_safe(payload), sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _tracking_token(payload: dict) -> str:
    return _clean(_dict(payload.get("clientUtm")).get("utm_content") or payload.get("metadataToken"))


def _product_id(payload: dict) -> str:
    product = _dict(payload.get("product"))
    return _clean(payload.get("productId") or product.get("id") or product.get("product_id"))


def _offer_id(payload: dict) -> str:
    product = _dict(payload.get("product"))
    return _clean(payload.get("offerId") or payload.get("offer_id") or product.get("offerId") or product.get("tier_id"))


def _uuid(value: Any) -> str | None:
    try:
        return str(UUID(_clean(value)))
    except ValueError:
        return None


def invoice_mismatch(order: CoinPurchase, payload: dict, *, from_create: bool = False,
                     require_amount: bool = True) -> str | None:
    invoice_id = extract_invoice_id(payload)
    amount, currency = extract_money(payload)
    if not invoice_id or (order.invoice_id and invoice_id != order.invoice_id):
        return "invoice_mismatch"

    if (amount is not None or require_amount) and amount != order.amount:
        return "amount_mismatch"

    if (currency or require_amount) and currency != order.currency:
        return "currency_mismatch"

    invoice_type = _clean(payload.get("type")).upper()
    if invoice_type and invoice_type != "INVOICE":
        return "invoice_type_mismatch"

    offer, product, token = _offer_id(payload), _product_id(payload), _tracking_token(payload)
    if offer and offer != order.offer_id:
        return "offer_mismatch"

    if product and order.product_id and product != order.product_id:
        return "product_mismatch"

    if token and token != order.tracking_token:
        return "tracking_mismatch"

    matches_purpose = invoice_type == "INVOICE" or offer == order.offer_id or (product and product == order.product_id)
    if not order.invoice_id and not from_create and not (token and token == order.tracking_token and matches_purpose):
        return "purpose_unconfirmed"

    return None


def _safe_url(value: Any) -> str | None:
    url = _clean(value)
    if not url or len(url) > 4096 or "\\" in url or any(char.isspace() for char in url):
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None

    return url if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else None


async def _request_lava(method: str, path: str, payload: dict | None = None) -> dict:
    key = _clean(settings.KASSA_API_KEY)
    if not key:
        raise HTTPException(503, detail="kassa_api_key_missing")

    headers = {"X-Api-Key": key, "Accept": "application/json", "Content-Type": "application/json"}
    content = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(method, API_BASE + path, headers=headers, content=content)
    except httpx.TimeoutException:
        raise HTTPException(504, detail="kassa_invoice_timeout") from None

    except httpx.HTTPError:
        raise HTTPException(502, detail="kassa_invoice_request_failed") from None

    if not response.is_success:
        if response.status_code in {401, 403}:
            detail, code = "kassa_api_unauthorized", 503
        elif response.status_code == 404:
            detail, code = "kassa_invoice_not_found", 404
        elif response.status_code == 429:
            detail, code = "kassa_rate_limited", 429
        else:
            detail, code = "kassa_request_rejected", 422 if response.status_code in {400, 422} else 502
        raise HTTPException(code, detail=detail)
    try:
        data = json.loads(response.text, parse_float=Decimal)
    except ValueError:
        raise HTTPException(502, detail="kassa_invoice_invalid_response") from None

    if not isinstance(data, dict):
        raise HTTPException(502, detail="kassa_invoice_invalid_response")

    return data


async def current_coin_packages(session: AsyncSession) -> dict[str, dict[str, str]]:
    row = await session.get(AppSettings, 1, populate_existing=True)
    try:
        return parse_dc_packages(row.dc_coin_packages if row else None)

    except (KeyError, ValueError) as exc:
        raise HTTPException(503, detail="dc_price_invalid") from exc


def _configured_offer(quantity: int) -> str | None:
    configured = _clean(getattr(settings, f"KASSA_COIN_OFFER_{quantity}_ID", ""))
    if not configured:
        return None

    offer_id = _uuid(configured)
    if offer_id is None:
        raise HTTPException(503, detail="kassa_coin_offer_invalid")

    offers = [_uuid(getattr(settings, f"KASSA_COIN_OFFER_{pack}_ID", "")) for pack in DC_PACKAGE_QUANTITIES]
    if offers.count(offer_id) != 1:
        raise HTTPException(503, detail="kassa_coin_offer_invalid")

    return offer_id


def _offer_matches_prices(offer: dict, expected: dict[str, str]) -> bool:
    if offer.get("recurrent"):
        return False

    rows = offer.get("prices")
    if not isinstance(rows, list) or len(rows) != len(DC_CURRENCIES):
        return False

    prices = {}
    for row in rows:
        row = _dict(row)
        currency = _clean(row.get("currency")).upper()
        if currency in prices or row.get("periodicity") not in (None, "ONE_TIME"):
            return False

        prices[currency] = decimal_money(row.get("amount"))
    return prices == {currency: Decimal(expected[currency]) for currency in DC_CURRENCIES}


async def _resolve_coin_offer(product_id: str, expected_prices: dict[str, str]) -> str:
    path = "/api/v2/products?feedVisibility=ALL"
    for _ in range(20):
        page = await _request_lava("GET", path)
        items = page.get("items")
        if not isinstance(items, list):
            break

        for item in items:
            item = _dict(item)
            product = _dict(item.get("data")) if "data" in item else item
            if _uuid(product.get("id")) != product_id:
                continue
            offers = product.get("offers")
            if product.get("type") == "SUBSCRIPTION" or not isinstance(offers, list):
                raise HTTPException(503, detail="kassa_coin_offer_invalid")

            matches = [_uuid(_dict(offer).get("id")) for offer in offers
                       if _offer_matches_prices(_dict(offer), expected_prices)]
            if len(matches) != 1 or matches[0] is None:
                raise HTTPException(503, detail="kassa_coin_offer_prices_mismatch")

            return matches[0]

        parsed = urlsplit(_safe_url(page.get("nextPage")) or "")
        if parsed.netloc != "gate.lava.top" or parsed.path != "/api/v2/products" or not parsed.query:
            break

        query = dict(parse_qsl(parsed.query))
        query["feedVisibility"] = "ALL"
        next_path = parsed.path + "?" + urlencode(query)
        if next_path == path:
            break

        path = next_path
    raise HTTPException(503, detail="kassa_coin_offer_missing")


def order_response(order: CoinPurchase, balance: int) -> dict:
    if order.status == "processed" and order.result:
        return dict(order.result)

    return {"order_id": order.id, "status": order.status, "payment_url": order.payment_url,
            "invoice_id": order.invoice_id, "dc_balance": int(balance), "quantity": order.quantity,
            "unit_price": format(order.unit_price, ".2f") if order.unit_price is not None else None,
            "amount": format(order.amount, ".2f") if order.amount is not None else None,
            "currency": order.currency, "email": order.email, "request_id": order.request_id}


async def create_coin_invoice(session: AsyncSession, *, user_id: int, payload) -> dict:
    if not isinstance(payload.quantity, int) or isinstance(payload.quantity, bool) or payload.quantity not in DC_PACKAGE_QUANTITIES:
        raise HTTPException(422, detail="dc_package_invalid")

    request_id = str(payload.request_id)
    existing_id = await session.scalar(select(CoinPurchase.id).where(CoinPurchase.request_id == request_id))
    offer_id = None
    product_id = _uuid(settings.KASSA_COIN_PRODUCT_ID)
    if existing_id is None:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(404, detail="user_not_found")

        await ensure_purchase_access(session, user)
        if not _clean(settings.KASSA_API_KEY):
            raise HTTPException(503, detail="kassa_api_key_missing")

        offer_id = _configured_offer(payload.quantity)
        if _clean(settings.KASSA_COIN_PRODUCT_ID) and product_id is None:
            raise HTTPException(503, detail="kassa_coin_offer_invalid")

        packages = await current_coin_packages(session)
        prices = packages[str(payload.quantity)]
        amount = Decimal(prices[payload.currency])
        if amount != payload.expected_amount:
            raise HTTPException(409, detail={"code": "dc_price_changed", "amount": format(amount, ".2f"),
                                            "quantity": payload.quantity, "currency": payload.currency})

        await session.commit()
        if offer_id is None:
            if product_id is None:
                raise HTTPException(503, detail="kassa_coin_offer_missing")

            if list(packages.values()).count(prices) != 1:
                raise HTTPException(503, detail="kassa_coin_offer_prices_mismatch")

            offer_id = await _resolve_coin_offer(product_id, prices)
    user = await lock_user_balance(session, user_id)
    await lock_dc_request(session, request_id, journal="coin")
    await ensure_purchase_access(session, user)
    existing = await session.scalar(select(CoinPurchase).where(CoinPurchase.request_id == request_id))
    email = str(payload.email).strip().lower()
    if not EMAIL_RE.fullmatch(email) or len(email) > 254:
        raise HTTPException(422, detail="kassa_email_invalid")

    if existing:
        if (existing.user_id != user_id or existing.quantity != payload.quantity or existing.currency != payload.currency
                or existing.email != email or existing.amount != payload.expected_amount):
            raise HTTPException(409, detail="idempotency_conflict")

        result = order_response(existing, user.dc_balance)
        await session.commit()
        if existing.status == "processed":
            await notify_coin_operation(session, existing)
        return result

    if offer_id is None:
        raise HTTPException(409, detail="idempotency_conflict")

    amount = Decimal((await current_coin_packages(session))[str(payload.quantity)][payload.currency])
    if amount != payload.expected_amount:
        raise HTTPException(409, detail={"code": "dc_price_changed", "amount": format(amount, ".2f"),
                                        "quantity": payload.quantity, "currency": payload.currency})

    order = CoinPurchase(user_id=user_id, source="lava", quantity=payload.quantity,
                         amount=amount, currency=payload.currency, email=email,
                         request_id=request_id, status="creating", offer_id=offer_id,
                         product_id=product_id, tracking_token="dc_" + token_urlsafe(24), event_log=[])
    session.add(order)
    await session.flush()
    return_base = f"https://{settings.DOMAIN}/profile?tab=subscription&order_id={order.id}&dc_payment="
    request_payload = {"email": email, "offerId": offer_id, "currency": order.currency,
                       "buyerLanguage": "RU",
                       "clientUtm": {"utm_source": "mafia_site", "utm_medium": "dc", "utm_campaign": "dc_purchase",
                                     "utm_term": str(user_id), "utm_content": order.tracking_token},
                       "successful_return_url": return_base + "success", "failure_return_url": return_base + "fail",
                       "cancel_return_url": return_base + "cancelled"}
    order.request_payload = request_payload
    order.result = order_response(order, user.dc_balance)
    await session.commit()
    try:
        invoice = await _request_lava("POST", "/api/v3/invoice", request_payload)
    except HTTPException as exc:
        user = await lock_user_balance(session, user_id)
        order = await session.scalar(select(CoinPurchase).where(CoinPurchase.id == order.id).with_for_update().execution_options(populate_existing=True))
        if order.status != "processed":
            order.status = "failed" if exc.status_code in {422, 404, 503} else "unknown"
            order.provider_payload = {"creation_error": exc.detail}
            order.result = order_response(order, user.dc_balance)
        await session.commit()
        return order_response(order, user.dc_balance)

    return await apply_invoice_payload(session, order_id=order.id, payload=invoice, from_create=True)


async def _append_event(order: CoinPurchase, payload: dict) -> bool:
    key = provider_event_key(payload)
    events = list(order.event_log or [])
    if any(row.get("key") == key for row in events):
        return False

    order.event_log = [*events, {"key": key, "received_at": datetime.now(timezone.utc).isoformat(), "payload": json_safe(payload)}]
    return True


async def apply_invoice_payload(session: AsyncSession, *, order_id: int, payload: dict, from_create: bool = False) -> dict:
    preview = await session.get(CoinPurchase, order_id)
    if preview is None or preview.user_id is None:
        raise HTTPException(404, detail="coin_order_not_found")

    if await session.get(User, preview.user_id) is None:
        order = await session.scalar(select(CoinPurchase).where(CoinPurchase.id == order_id).with_for_update().execution_options(populate_existing=True))
        await _append_event(order, payload)
        order.provider_payload = {"reason": "user_not_found", "payload": json_safe(payload)}
        order.status = "unknown"
        await session.commit()
        return order_response(order, 0)

    user = await lock_user_balance(session, preview.user_id)
    order = await session.scalar(select(CoinPurchase).where(CoinPurchase.id == order_id).with_for_update().execution_options(populate_existing=True))
    await _append_event(order, payload)
    kind = event_type(payload)
    if kind in REFUND_EVENTS:
        await session.commit()
        return order_response(order, user.dc_balance)

    if order.processed_at is not None:
        result = order_response(order, user.dc_balance)
        await session.commit()
        await notify_coin_operation(session, order)
        return result

    if kind and kind not in {"payment.success", "payment.failed"}:
        await session.commit()
        return order_response(order, user.dc_balance)

    invoice_id = extract_invoice_id(payload)
    state = _clean(payload.get("status")).lower().replace("-", "_")
    paid = state in SUCCESS_STATUSES if not kind else kind == "payment.success" and (not state or state in SUCCESS_STATUSES)
    mismatch = invoice_mismatch(order, payload, from_create=from_create, require_amount=from_create or paid or not order.invoice_id)
    if not mismatch and not order.invoice_id:
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "dc:invoice:" + invoice_id})
        collision = await session.scalar(select(CoinPurchase.id).where(CoinPurchase.invoice_id == invoice_id, CoinPurchase.id != order.id))
        if collision:
            mismatch = "invoice_mismatch"
        else:
            order.invoice_id = invoice_id
    order.provider_payload = json_safe(payload)
    if mismatch:
        order.status = "review" if paid and mismatch not in {"invoice_mismatch", "tracking_mismatch", "purpose_unconfirmed"} else "unknown"
        order.provider_payload = {"reason": mismatch, "payload": json_safe(payload)}
    elif paid:
        if user.deleted_at is not None:
            order.status = "review"
            order.provider_payload = {"reason": "user_deleted", "payload": json_safe(payload)}
        else:
            order.invoice_id = invoice_id
            order.balance_before = user.dc_balance
            user.dc_balance = checked_balance(user.dc_balance, order.quantity)
            order.balance_after = user.dc_balance
            order.processed_at = datetime.now(timezone.utc)
            order.status = "processed"
    elif kind == "payment.failed" or state in FAILED_STATUSES:
        order.status = "failed"
    elif not kind and state in PENDING_STATUSES:
        order.status = "pending"
    else:
        order.status = "unknown"
    if from_create and not mismatch:
        order.payment_url = _safe_url(payload.get("paymentUrl") or payload.get("payment_url"))
    if order.status == "pending" and not order.payment_url:
        order.status = "unknown"
    order.result = None
    order.result = order_response(order, user.dc_balance)
    result = dict(order.result)
    note = await persist_coin_operation_notice(session, order)
    await session.commit()
    if order.status == "processed":
        await notify_coin_operation(session, order, note=note)
    return result


async def list_coin_invoices(session: AsyncSession, *, user_id: int) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(401, detail="Unauthorized")

    rows = (await session.scalars(select(CoinPurchase).where(CoinPurchase.user_id == user_id, CoinPurchase.source == "lava")
                                  .order_by(CoinPurchase.created_at.desc(), CoinPurchase.id.desc()).limit(50))).all()
    balance = await get_dc_balance(session, user_id)
    return {"items": [order_response(order, balance) for order in rows]}


async def _find_completed_invoice(*, email: str, token: str, created_at: datetime) -> dict | None:
    query = {"buyerEmail": email, "beginDate": (created_at - timedelta(minutes=1)).isoformat(),
             "invoiceTypes": "INVOICE", "invoiceStatuses": "COMPLETED", "size": 50}
    for number in range(1, 4):
        page = await _request_lava("GET", "/api/v2/invoices?" + urlencode({**query, "page": number}))
        items = page.get("items")
        if not isinstance(items, list):
            return None

        for payload in items:
            if (isinstance(payload, dict) and _tracking_token(payload) == token
                    and payload.get("type") == "INVOICE" and payload.get("status") == "COMPLETED"):
                return payload

        if len(items) < query["size"]:
            break

    return None


async def check_coin_invoice(session: AsyncSession, *, user_id: int, order_id: int) -> dict:
    order = await session.scalar(select(CoinPurchase).where(CoinPurchase.id == order_id, CoinPurchase.user_id == user_id, CoinPurchase.source == "lava"))
    if order is None:
        raise HTTPException(404, detail="coin_order_not_found")

    if order.status == "processed":
        result = order_response(order, await get_dc_balance(session, user_id))
        await session.commit()
        await notify_coin_operation(session, order)
        return result

    invoice_id, email, token, created_at = order.invoice_id, order.email, order.tracking_token, order.created_at
    balance = await get_dc_balance(session, user_id)
    snapshot = order_response(order, balance)
    await session.commit()
    if not invoice_id and (not email or not token or created_at > datetime.now(timezone.utc) - timedelta(seconds=30)):
        return snapshot

    try:
        if invoice_id:
            payload = await _request_lava("GET", "/api/v2/invoices/" + quote(invoice_id, safe=""))
        else:
            payload = await _find_completed_invoice(email=email, token=token, created_at=created_at)
    except HTTPException:
        user = await lock_user_balance(session, user_id)
        order = await session.scalar(select(CoinPurchase).where(CoinPurchase.id == order_id).with_for_update().execution_options(populate_existing=True))
        if order.processed_at is None and order.status != "failed":
            order.status = "unknown"
        result = order_response(order, user.dc_balance)
        await session.commit()
        return result

    if payload is not None:
        return await apply_invoice_payload(session, order_id=order_id, payload=payload)

    await session.execute(update(CoinPurchase).where(
        CoinPurchase.id == order_id, CoinPurchase.invoice_id.is_(None), CoinPurchase.status == "creating"
    ).values(status="unknown"))
    order = await session.get(CoinPurchase, order_id, populate_existing=True)
    result = order_response(order, await get_dc_balance(session, user_id))
    await session.commit()
    return result


async def reconcile_coin_invoices(session: AsyncSession, *, limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    due = now - timedelta(minutes=1)
    rows = list((await session.execute(
        select(CoinPurchase.id, CoinPurchase.user_id, CoinPurchase.invoice_id)
        .where(CoinPurchase.source == "lava", CoinPurchase.updated_at < due,
               CoinPurchase.processed_at.is_(None),
               or_(CoinPurchase.status.in_(("pending", "unknown", "review", "creating")),
                   and_(CoinPurchase.status == "failed", CoinPurchase.invoice_id.is_not(None),
                        CoinPurchase.created_at >= now - timedelta(days=1))),
               or_(CoinPurchase.invoice_id.is_not(None), and_(CoinPurchase.created_at >= now - timedelta(days=30),
                        CoinPurchase.updated_at < now - timedelta(minutes=15))))
        .order_by(CoinPurchase.updated_at.asc(), CoinPurchase.id.asc()).limit(max(1, min(limit, 100)))
    )).all())
    await session.commit()
    completed = 0
    for order_id, uid, invoice_id in rows:
        if uid is None:
            continue
        try:
            cutoff = due if invoice_id else now - timedelta(minutes=15)
            claimed = await session.scalar(update(CoinPurchase).where(
                CoinPurchase.id == order_id, CoinPurchase.updated_at < cutoff, CoinPurchase.processed_at.is_(None)
            ).values(updated_at=now).returning(CoinPurchase.id))
            await session.commit()
            if claimed is None:
                continue
            response = await check_coin_invoice(session, user_id=uid, order_id=order_id)
            completed += int(response["status"] == "processed")
        except Exception:
            await session.rollback()
            log.exception("dc.invoice_reconcile_failed", order_id=order_id)
    return completed


def _ensure_webhook_authorized(request: Request, *, x_api_key: str | None, x_webhook_secret: str | None, authorization: str | None) -> None:
    expected = _clean(settings.KASSA_WEBHOOK_SECRET)
    if not expected:
        raise HTTPException(503, detail="kassa_webhook_secret_missing")

    auth = _clean(authorization)
    candidates = [_clean(x_api_key), _clean(x_webhook_secret), *[_clean(request.query_params.get(name)) for name in ("token", "key", "secret")]]
    if auth.lower().startswith("bearer "):
        candidates.append(auth[7:].strip())
    if auth.lower().startswith("basic "):
        with suppress(ValueError, UnicodeDecodeError):
            decoded = base64.b64decode(auth[6:].strip(), validate=True).decode()
            candidates.extend((decoded, decoded.partition(":")[2]))
    if not any(value and compare_digest(value.encode(), expected.encode()) for value in candidates):
        raise HTTPException(401, detail="Unauthorized")


async def process_kassa_webhook(session: AsyncSession, *, request: Request, payload: dict[str, Any],
                                x_api_key: str | None, x_webhook_secret: str | None, authorization: str | None) -> None:
    _ensure_webhook_authorized(request, x_api_key=x_api_key, x_webhook_secret=x_webhook_secret, authorization=authorization)
    invoice_id, token = extract_invoice_id(payload), _tracking_token(payload)
    clauses = []
    if invoice_id:
        clauses.append(CoinPurchase.invoice_id == invoice_id)
    if token:
        clauses.append(CoinPurchase.tracking_token == token)
    matches = list((await session.scalars(select(CoinPurchase).where(or_(*clauses), CoinPurchase.source == "lava"))).all()) if clauses else []
    if len(matches) == 1:
        await apply_invoice_payload(session, order_id=matches[0].id, payload=payload)
        return

    key = provider_event_key(payload)
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "dc:event:" + key})
    if not await session.scalar(select(CoinPurchase.id).where(CoinPurchase.provider_event_id == key)):
        amount, currency = extract_money(payload)
        session.add(CoinPurchase(source="provider_event", quantity=0, status="unmatched", provider_event_id=key,
                                 amount=amount if amount is not None and amount <= Decimal("9999999999999999.99") else None,
                                 currency=currency if len(currency) == 3 else None, provider_payload=json_safe(payload),
                                 event_log=[{"key": key, "payload": json_safe(payload)}]))
    await session.commit()
