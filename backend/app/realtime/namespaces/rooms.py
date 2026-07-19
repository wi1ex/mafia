from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import get_rooms_brief, validate_auth, filter_rooms_for_viewer
from ..connections import register_user_socket, unregister_user_socket
from ...core.clients import get_redis
from ...core.roles import ROLE_ADMIN, ROLE_MODER, normalize_user_role
from ...security.decorators import rate_limited_sio
from ...schemas.realtime import RoomsListAck

log = structlog.get_logger()


@sio.event(namespace="/rooms")
async def connect(sid, environ, auth):
    role = "user"
    uid = 0
    vr = None
    token = auth.get("token") if isinstance(auth, dict) else None
    if token:
        vr = await validate_auth(auth)
        if not vr:
            log.warning("rooms.connect.denied", sid=sid)
            return False

        uid, role = vr[0], vr[1]

    await sio.save_session(
        sid,
        {
            "uid": uid,
            "role": role,
            "auth_sid": vr.auth_sid if token and vr else "",
            "auth_expires_at": vr.expires_at if token and vr else 0,
        },
        namespace="/rooms",
    )
    if uid and vr:
        await register_user_socket(
            user_id=uid,
            socket_sid=sid,
            namespace="/rooms",
            auth_sid=vr.auth_sid,
        )
        await sio.enter_room(sid, f"user:{uid}", namespace="/rooms")
    role = normalize_user_role(role)
    if role == ROLE_ADMIN:
        await sio.enter_room(sid, "role:admin", namespace="/rooms")
    elif role == ROLE_MODER:
        await sio.enter_room(sid, "role:moder", namespace="/rooms")


@sio.event(namespace="/rooms")
@rate_limited_sio(
    lambda sid, uid=None, **__: f"rl:sio:rooms_list:{uid or sid}",
    limit=20,
    window_s=1,
    session_ns="/rooms",
    auth_optional=True,
)
async def rooms_list(sid) -> RoomsListAck:
    try:
        role = "user"
        uid = 0
        try:
            sess = await sio.get_session(sid, namespace="/rooms")
            role = str((sess or {}).get("role") or "user")
            uid = int((sess or {}).get("uid") or 0)
        except Exception:
            role = "user"
            uid = 0

        r = get_redis()
        rids = list(map(int, await r.zrevrange("rooms:index", 0, 99)))
        if not rids:
            return {"ok": True, "rooms": []}

        rooms = await get_rooms_brief(r, rids)
        rooms = await filter_rooms_for_viewer(r, rooms, role, uid)

        return {"ok": True, "rooms": rooms}

    except Exception:
        log.exception("rooms.list.error", sid=sid)
        return {"ok": False, "rooms": []}


@sio.event(namespace="/rooms")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/rooms")
        uid = int((sess or {}).get("uid") or 0)
    except Exception:
        uid = 0
    if uid > 0:
        await unregister_user_socket(user_id=uid, socket_sid=sid, namespace="/rooms")
