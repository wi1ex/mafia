from __future__ import annotations
from collections.abc import Mapping
from ipaddress import ip_address
import json
import logging
import re
import sys
from typing import Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.log import AppLog


_BROWSER_ID_RE = re.compile(r"[0-9a-fA-F]{32}")
_UNAVAILABLE = "—"


def trusted_client_ip(headers: Mapping[str, str], client_host: str | None = None) -> str:
    for candidate in (headers.get("x-real-ip", ""), client_host):
        try:
            return str(ip_address(str(candidate or "").strip()))
        except ValueError:
            continue

    return "unknown"


def configure_logging() -> None:
    pre = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    structlog.configure(
        processors=[*pre, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(), foreign_pre_chain=pre
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def append_auth_log_metadata(details: str, *, headers: Mapping[str, str], client_host: str | None = None) -> str:
    raw_browser_id = headers.get("x-browser-id", "")
    browser_id = (
        raw_browser_id.lower()
        if _BROWSER_ID_RE.fullmatch(raw_browser_id)
        else _UNAVAILABLE
    )

    client_ip = trusted_client_ip(headers, client_host)
    if client_ip == "unknown":
        client_ip = _UNAVAILABLE

    return f"{details} | browser_id={browser_id} | ip={client_ip}"


async def log_action(db: AsyncSession, *, user_id: int | None, username: str | None, action: str, details: str | dict[str, Any], commit: bool = True) -> None:
    if isinstance(details, (dict, list)):
        try:
            details = json.dumps(details, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            details = str(details)

    db.add(AppLog(user_id=user_id, username=username, action=action, details=details or ""))
    if commit:
        await db.commit()
