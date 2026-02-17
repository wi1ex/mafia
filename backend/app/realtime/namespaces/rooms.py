from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import get_rooms_brief, validate_auth, filter_rooms_for_role
from ...core.clients import get_redis
from ...security.decorators import rate_limited_sio
from ...schemas.realtime import RoomsListAck

log = structlog.get_logger()


@sio.event(namespace="/rooms")
async def connect(sid, environ, auth):
    role = "user"
    uid = 0
    token = auth.get("token") if isinstance(auth, dict) else None
    if token:
        vr = await validate_auth(auth)
        if vr:
            uid, role, _, _ = vr

    await sio.save_session(sid, {"uid": uid, "role": role}, namespace="/rooms")
    if uid:
        await sio.enter_room(sid, f"user:{uid}", namespace="/rooms")
    if role == "admin":
        await sio.enter_room(sid, "role:admin", namespace="/rooms")


@rate_limited_sio(lambda sid, **__: f"rl:sio:rooms_list:{sid}", limit=10, window_s=1)
@sio.event(namespace="/rooms")
async def rooms_list(sid) -> RoomsListAck:
    try:
        role = "user"
        try:
            sess = await sio.get_session(sid, namespace="/rooms")
            role = str((sess or {}).get("role") or "user")
        except Exception:
            role = "user"

        r = get_redis()
        rids = list(map(int, await r.zrevrange("rooms:index", 0, 99)))
        if not rids:
            return {"ok": True, "rooms": []}

        rooms = await get_rooms_brief(r, rids)
        rooms = filter_rooms_for_role(rooms, role)

        return {"ok": True, "rooms": rooms}

    except Exception:
        log.exception("rooms.list.error", sid=sid)
        return {"ok": False, "rooms": []}
