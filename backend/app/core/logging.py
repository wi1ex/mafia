from __future__ import annotations
import logging
import sys
from typing import Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.log import AppLog


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
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer(), foreign_pre_chain=pre))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


async def log_action(db: AsyncSession, *, user_id: int | None, username: str | None, action: str, details: dict[str, Any]) -> None:
    db.add(AppLog(user_id=user_id, username=username, action=action, details=details))
    await db.commit()
