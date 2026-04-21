from __future__ import annotations
from time import time
import structlog
from sqlalchemy import func, update
from ..core.clients import get_redis
from ..core.db import SessionLocal
from ..core.settings import settings
from ..models.user import User

log = structlog.get_logger()


async def touch_user_activity(user_id: int, *, force_db: bool = False) -> None:
    try:
        uid = int(user_id)
    except Exception:
        return

    if uid <= 0:
        return

    should_touch_db = bool(force_db)
    r = None
    try:
        r = get_redis()
        await r.zadd("online:users:seen", {str(uid): int(time())})
    except Exception:
        r = None
        log.warning("presence.online_touch_failed", uid=uid)

    if r is not None:
        try:
            ttl = max(1, int(settings.ONLINE_TTL_SECONDS))
            if should_touch_db:
                await r.set(f"user:{uid}:last_visit_touch", "1", ex=ttl)
            else:
                should_touch_db = bool(await r.set(f"user:{uid}:last_visit_touch", "1", ex=ttl, nx=True))
        except Exception:
            log.warning("presence.last_visit_throttle_failed", uid=uid)

    if not should_touch_db:
        return

    try:
        async with SessionLocal() as db:
            await db.execute(update(User).where(User.id == uid).values(last_visit_at=func.now()))
            await db.commit()
    except Exception:
        log.warning("presence.last_visit_touch_failed", uid=uid)
