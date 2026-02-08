from __future__ import annotations
import structlog
from ..core.clients import get_httpx
from ..core.settings import settings

log = structlog.get_logger()


async def send_telegram_message(chat_id: int, text: str) -> bool:
    token = (settings.TG_BOT_TOKEN or "").strip()
    if not token:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": int(chat_id),
        "text": text,
        "disable_web_page_preview": True,
    }

    try:
        resp = await get_httpx().post(url, json=payload)
        return resp.status_code == 200

    except Exception as e:
        log.warning("telegram.send_failed", err=type(e).__name__)
        return False
