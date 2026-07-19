from __future__ import annotations
import structlog
from ..sio import sio
from ..utils import validate_auth
from ..connections import register_user_socket, unregister_user_socket
from ...api.utils import check_sanctions_expired, emit_auth_profile_sync
from ...security.decorators import rate_limited_sio
from ...services.presence import touch_user_activity
from ...services.global_chat import emit_global_chat_unread_count

log = structlog.get_logger()


@sio.event(namespace="/auth")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        log.warning("auth.connect.denied", sid=sid)
        return False

    uid = vr.user_id
    await touch_user_activity(uid, force_db=True)
    await sio.save_session(sid,
                           {
                               "uid": uid,
                               "role": vr.role,
                               "auth_sid": vr.auth_sid,
                               "auth_expires_at": vr.expires_at,
                           },
                           namespace="/auth")
    await register_user_socket(
        user_id=uid,
        socket_sid=sid,
        namespace="/auth",
        auth_sid=vr.auth_sid,
    )
    await sio.enter_room(sid,
                         f"user:{uid}",
                         namespace="/auth")
    try:
        await emit_global_chat_unread_count(uid)
    except Exception:
        log.warning("auth.connect.chat_unread_count_failed", uid=uid)
    try:
        await emit_auth_profile_sync(uid, role=str(vr[1]))
    except Exception:
        log.warning("auth.connect.profile_sync_failed", uid=uid)


@sio.event(namespace="/auth")
@rate_limited_sio(
    lambda *, uid=None, **__: f"rl:sio:online_ping:{uid or 'nouid'}",
    limit=30,
    window_s=60,
    session_ns="/auth",
)
async def online_ping(sid, data=None):
    try:
        sess = await sio.get_session(sid, namespace="/auth")
        uid = int(sess.get("uid") or 0)
    except Exception:
        uid = 0

    if not uid:
        return

    await touch_user_activity(uid)
    try:
        await check_sanctions_expired(uid)
    except Exception:
        log.warning("auth.ping.sanctions_check_failed", uid=uid)


@sio.event(namespace="/auth")
async def disconnect(sid):
    try:
        sess = await sio.get_session(sid, namespace="/auth")
        uid = int(sess.get("uid") or 0)
    except Exception:
        uid = 0

    if not uid:
        return

    await unregister_user_socket(user_id=uid, socket_sid=sid, namespace="/auth")
    await touch_user_activity(uid, force_db=True)

    return
