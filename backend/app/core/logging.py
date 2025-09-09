from __future__ import annotations
import sys
import logging
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.log import AppLog


def configure_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            timestamper,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    # Стандартный логгер на stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Уменьшаем болтовню uvicorn access
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

async def log_action(db: AsyncSession, *, user_id: int | None, username: str | None, action: str, details: dict):
    db.add(AppLog(user_id=user_id, username=username, action=action, details=details))
    await db.flush()
