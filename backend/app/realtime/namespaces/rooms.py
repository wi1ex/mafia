from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import get_rooms_brief
from ...core.clients import get_redis
from ...security.decorators import rate_limited_sio
from ...schemas.realtime import RoomsListAck

log = structlog.get_logger()


@rate_limited_sio(lambda sid, **__: f"rl:sio:rooms_list:{sid}", limit=5, window_s=1)
@sio.event(namespace="/rooms")
async def rooms_list(sid) -> RoomsListAck:
    try:
        r = get_redis()
        rids = list(map(int, await r.zrevrange("rooms:index", 0, 99)))
        if not rids:
            return {"ok": True, "rooms": []}

        rooms = await get_rooms_brief(r, rids)
        return {"ok": True, "rooms": rooms}

    except Exception:
        log.exception("rooms.list.error", sid=sid)
        return {"ok": False, "rooms": []}
