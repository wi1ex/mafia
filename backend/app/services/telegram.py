from __future__ import annotations
import httpx
import structlog
import asyncio
from dataclasses import dataclass
from ..core.settings import settings

log = structlog.get_logger()

TELEGRAM_API_TIMEOUT_S = 10
TELEGRAM_API_RETRY_ATTEMPTS = 3


@dataclass(frozen=True)
class TelegramSendResult:
    ok: bool
    reason: str | None = None


def _is_chat_unavailable(*, status_code: int, description: str) -> bool:
    text = (description or "").lower()
    if status_code == 403:
        return True

    if "chat not found" in text:
        return True

    if "bot was blocked by the user" in text:
        return True

    if "user is deactivated" in text:
        return True

    return False


def _extract_description(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""

    raw = payload.get("description")
    return str(raw or "")


def _extract_retry_after_seconds(payload: object, headers: httpx.Headers) -> float:
    if isinstance(payload, dict):
        params = payload.get("parameters")
        if isinstance(params, dict):
            try:
                retry_after = float(params.get("retry_after") or 0)
            except Exception:
                retry_after = 0.0
            if retry_after > 0:
                return retry_after

    try:
        retry_after_header = float(headers.get("retry-after") or 0)
    except Exception:
        retry_after_header = 0.0

    return retry_after_header if retry_after_header > 0 else 0.0


async def send_text_message(*, chat_id: int, text: str) -> TelegramSendResult:
    token = (settings.TG_BOT_TOKEN or "").strip()
    if not token:
        log.warning("telegram.send.skipped_no_token")
        return TelegramSendResult(ok=False, reason="telegram_not_configured")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": int(chat_id),
        "text": text,
        "disable_web_page_preview": True,
    }

    async with httpx.AsyncClient(timeout=TELEGRAM_API_TIMEOUT_S) as client:
        for attempt in range(1, TELEGRAM_API_RETRY_ATTEMPTS + 1):
            try:
                resp = await client.post(url, json=payload)
                try:
                    data = resp.json()
                except Exception:
                    data = {}
            except httpx.HTTPError:
                if attempt < TELEGRAM_API_RETRY_ATTEMPTS:
                    wait_s = 0.5 * attempt
                    log.warning("telegram.send.network_retry", attempt=attempt, wait_s=wait_s)
                    await asyncio.sleep(wait_s)
                    continue

                log.warning("telegram.send.network_failed", attempt=attempt, exc_info=True)
                return TelegramSendResult(ok=False, reason="telegram_unavailable")

            ok = bool(isinstance(data, dict) and data.get("ok") is True and resp.status_code == 200)
            if ok:
                return TelegramSendResult(ok=True, reason=None)

            description = _extract_description(data)
            if _is_chat_unavailable(status_code=resp.status_code, description=description):
                log.info(
                    "telegram.send.chat_unavailable",
                    status_code=resp.status_code,
                    description=description,
                )
                return TelegramSendResult(ok=False, reason="telegram_chat_unavailable")

            retryable = resp.status_code in {429, 500, 502, 503, 504}
            if retryable and attempt < TELEGRAM_API_RETRY_ATTEMPTS:
                retry_after = _extract_retry_after_seconds(data, resp.headers)
                wait_s = retry_after if retry_after > 0 else 0.5 * attempt
                log.warning(
                    "telegram.send.retryable",
                    status_code=resp.status_code,
                    attempt=attempt,
                    wait_s=wait_s,
                    description=description,
                )
                await asyncio.sleep(wait_s)
                continue

            log.warning(
                "telegram.send.failed",
                status_code=resp.status_code,
                attempt=attempt,
                description=description,
            )
            return TelegramSendResult(ok=False, reason="telegram_unavailable")

    return TelegramSendResult(ok=False, reason="telegram_unavailable")
