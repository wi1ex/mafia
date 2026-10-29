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
_REDACTED = "[REDACTED]"
_SENSITIVE_LOG_KEYS = frozenset({
    "authorization", "proxy_authorization", "cookie", "set_cookie",
    "access_token", "refresh_token", "token", "password", "secret",
    "api_key", "api_secret", "tg_bot_token", "bot_api_token",
    "jwt_secret_key", "livekit_api_secret",
})
_TELEGRAM_CREDENTIAL_RE = re.compile(r"(https?://api\.telegram\.org/(?:file/)?bot)[^/\s?\"'<>]+", re.IGNORECASE)
_RTC_QUERY_RE = re.compile(r"(/rtc(?:/[a-zA-Z0-9/_-]*)?\?)[^\s\"'<>]+")
_BEARER_RE = re.compile(r"(\bBearer\s+)[^\s,;\"'<>]+", re.IGNORECASE)
_AUTHORIZATION_RE = re.compile(r"(\b(?:proxy[-_])?authorization\b[\"']?\s*[:=]\s*[\"']?)[^\"'\\\r\n,;}]+", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b")
_QUOTED_SECRET_VALUE_RE = re.compile(
    r"(\b(?:access_token|refresh_token|api_key|api_secret|password|secret|token)\b[\"']?\s*[:=]\s*)([\"'])(.*?)\2",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(\b(?:access_token|refresh_token|api_key|api_secret|password|secret|token)\b[\"']?\s*[:=]\s*)[^\"'\\\s,;&<>}]+",
    re.IGNORECASE,
)


def redact_log_text(text: str) -> str:
    text = _TELEGRAM_CREDENTIAL_RE.sub(lambda match: match[1] + _REDACTED, text)
    text = _RTC_QUERY_RE.sub(lambda match: match[1] + _REDACTED, text)
    text = _BEARER_RE.sub(lambda match: match[1] + _REDACTED, text)
    text = _AUTHORIZATION_RE.sub(lambda match: match[1] + _REDACTED, text)
    text = _JWT_RE.sub(_REDACTED, text)
    text = _QUOTED_SECRET_VALUE_RE.sub(lambda match: match[1] + match[2] + _REDACTED + match[2], text)
    return _SECRET_VALUE_RE.sub(lambda match: match[1] + _REDACTED, text)


def _redact_log_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_log_text(value)

    if isinstance(value, Mapping):
        return {
            key: _REDACTED if str(key).lower().replace("-", "_") in _SENSITIVE_LOG_KEYS else _redact_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_log_value(item) for item in value]

    return value


def _redact_log_event(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return _redact_log_value(event_dict)


def _redacting_json_dumps(value: Any, **kwargs: Any) -> str:
    fallback = kwargs.get("default", repr)
    kwargs["default"] = lambda item: _redact_log_value(fallback(item))
    return json.dumps(_redact_log_value(value), **kwargs)


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
        _redact_log_event,
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
            processor=structlog.processors.JSONRenderer(serializer=_redacting_json_dumps), foreign_pre_chain=pre
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


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
