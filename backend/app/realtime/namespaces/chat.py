from __future__ import annotations
from uuid import UUID
import structlog
from fastapi import HTTPException
from ..sio import sio
from ..utils import validate_auth
from ...core.db import SessionLocal
from ...security.decorators import rate_limited_sio
from ...services.global_chat import (
    GLOBAL_CHAT_REACTIONS_ALLOWLIST,
    GLOBAL_CHAT_ROOM,
    build_global_chat_message_payload,
    create_global_chat_message,
    delete_global_chat_message,
    fetch_global_chat_context,
    fetch_global_chat_page,
    global_chat_open_user_room,
    get_global_chat_message,
    permissions_payload,
    resolve_global_chat_permissions,
    toggle_global_chat_reaction,
    validate_global_chat_send_input,
)
from ...services.text_moderation import enforce_clean_text

log = structlog.get_logger()


def _payload_dict(data: object) -> dict[str, object]:
    return data if isinstance(data, dict) else {}


def _positive_int(raw: object) -> int:
    try:
        value = int(raw)
    except Exception:
        return 0

    return value if value > 0 else 0


def _permissions_status(error: str | None) -> int:
    return 503 if error == "presence_unavailable" else 403


def _public_reactions(raw: list[dict[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for item in raw:
        emoji = str(item.get("emoji") or "")
        count = int(item.get("count") or 0)
        if not emoji or count <= 0:
            continue
        out.append({"emoji": emoji, "count": count})
    return out


@sio.event(namespace="/chat")
async def connect(sid, environ, auth):
    vr = await validate_auth(auth)
    if not vr:
        log.warning("chat.connect.denied", sid=sid)
        return False

    uid, role, username, avatar_name = vr
    await sio.save_session(
        sid,
        {
            "uid": uid,
            "role": role,
            "username": username,
            "avatar_name": avatar_name,
        },
        namespace="/chat",
    )
    await sio.enter_room(sid, f"user:{uid}", namespace="/chat")


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_open:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_open(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        limit = _positive_int(payload.get("limit"))

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {
                    "ok": False,
                    "status": _permissions_status(permissions.error),
                    "error": permissions.error or "forbidden",
                    "permissions": permissions_payload(permissions),
                }
        await sio.enter_room(sid, GLOBAL_CHAT_ROOM, namespace="/chat")
        await sio.enter_room(sid, global_chat_open_user_room(uid), namespace="/chat")
        async with SessionLocal() as db:
            messages, has_more, cursor_before_id = await fetch_global_chat_page(db, viewer_user_id=uid, limit=limit)
        return {
            "ok": True,
            "status": 200,
            "permissions": permissions_payload(permissions),
            "reactions_allowlist": list(GLOBAL_CHAT_REACTIONS_ALLOWLIST),
            "messages": messages,
            "has_more": has_more,
            "cursor_before_id": cursor_before_id,
        }
    except Exception:
        log.exception("chat.open.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_permissions:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_permissions(sid, data=None):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
        if not permissions.can_open:
            return {
                "ok": False,
                "status": _permissions_status(permissions.error),
                "error": permissions.error or "forbidden",
                "permissions": permissions_payload(permissions),
            }
        return {
            "ok": True,
            "status": 200,
            "permissions": permissions_payload(permissions),
        }
    except Exception:
        log.exception("chat.permissions.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_history:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_history(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        before_raw = payload.get("before_id") if "before_id" in payload else None
        before_id = _positive_int(before_raw)
        limit = _positive_int(payload.get("limit"))

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": _permissions_status(permissions.error), "error": permissions.error or "forbidden"}
            messages, has_more, cursor_before_id = await fetch_global_chat_page(
                db,
                viewer_user_id=uid,
                before_id=before_id if before_raw is not None else None,
                limit=limit,
            )
        return {
            "ok": True,
            "status": 200,
            "messages": messages,
            "has_more": has_more,
            "cursor_before_id": cursor_before_id,
        }
    except Exception:
        log.exception("chat.history.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_send:{uid or 'nouid'}", limit=5, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_send(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        raw_client_message_id = str(payload.get("client_message_id") or "").strip()
        if not raw_client_message_id:
            return {"ok": False, "status": 422, "error": "bad_client_message_id"}

        try:
            client_message_id = UUID(raw_client_message_id)
        except Exception:
            return {"ok": False, "status": 422, "error": "bad_client_message_id"}

        try:
            text, reply_to_message_id, image_object_key = await validate_global_chat_send_input(
                user_id=uid,
                text=payload.get("text"),
                reply_to_message_id=payload.get("reply_to_message_id"),
                image_object_key=payload.get("image_object_key"),
            )
        except ValueError as exc:
            return {"ok": False, "status": 422, "error": str(exc) or "bad_request"}

        if text.strip():
            try:
                enforce_clean_text(field="text", label="Сообщение", value=text)
            except HTTPException as exc:
                return {"ok": False, "status": exc.status_code, "error": "text_moderation", "detail": exc.detail}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": _permissions_status(permissions.error), "error": permissions.error or "forbidden"}
            if not permissions.can_send:
                if permissions.ban_active:
                    return {"ok": False, "status": 403, "error": "user_banned"}
                if permissions.timeout_active:
                    return {"ok": False, "status": 403, "error": "user_timeout"}
                return {"ok": False, "status": 403, "error": "forbidden"}

            if reply_to_message_id:
                reply_message = await get_global_chat_message(db, reply_to_message_id)
                if reply_message is None:
                    return {"ok": False, "status": 404, "error": "reply_not_found"}

            message, created = await create_global_chat_message(
                db,
                user_id=uid,
                client_message_id=client_message_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                image_object_key=image_object_key,
            )
            ack_message = await build_global_chat_message_payload(db, message_id=int(message.id), viewer_user_id=uid)
            public_message = await build_global_chat_message_payload(db, message_id=int(message.id), viewer_user_id=None)

        if created and public_message is not None:
            await sio.emit("chat_message_created", public_message, room=GLOBAL_CHAT_ROOM, namespace="/chat")

        return {
            "ok": True,
            "status": 200,
            "message": ack_message,
        }
    except Exception:
        log.exception("chat.send.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_react:{uid or 'nouid'}", limit=20, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_react_toggle(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        message_id = _positive_int(payload.get("message_id"))
        emoji = str(payload.get("emoji") or "")
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open or not permissions.can_react:
                return {"ok": False, "status": _permissions_status(permissions.error), "error": permissions.error or "forbidden"}

            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}
            if message.deleted_at is not None:
                return {"ok": False, "status": 409, "error": "message_deleted"}

            try:
                added = await toggle_global_chat_reaction(db, message_id=message_id, user_id=uid, emoji=emoji)
            except ValueError as exc:
                return {"ok": False, "status": 422, "error": str(exc) or "bad_request"}

            ack_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            public_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=None)

        if public_message is not None:
            await sio.emit(
                "chat_message_reactions_updated",
                {
                    "message_id": int(public_message["id"]),
                    "reactions": _public_reactions(public_message["reactions"]),
                },
                room=GLOBAL_CHAT_ROOM,
                namespace="/chat",
            )
        if ack_message is not None:
            await sio.emit(
                "chat_message_reactions_updated",
                {
                    "message_id": int(ack_message["id"]),
                    "reactions": ack_message["reactions"],
                },
                room=f"user:{uid}",
                namespace="/chat",
            )

        return {
            "ok": True,
            "status": 200,
            "message_id": message_id,
            "added": added,
            "reactions": ack_message["reactions"] if ack_message else [],
        }
    except Exception:
        log.exception("chat.react.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_delete:{uid or 'nouid'}", limit=10, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_delete(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        message_id = _positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_delete_own:
                return {"ok": False, "status": _permissions_status(permissions.error), "error": permissions.error or "forbidden"}

            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}
            if int(message.user_id) != uid:
                return {"ok": False, "status": 403, "error": "forbidden"}
            if message.deleted_at is not None:
                return {"ok": False, "status": 409, "error": "already_deleted"}

            await delete_global_chat_message(db, message=message, actor_user_id=uid)
            ack_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            public_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=None)

        if public_message is not None:
            await sio.emit("chat_message_deleted", public_message, room=GLOBAL_CHAT_ROOM, namespace="/chat")

        return {"ok": True, "status": 200, "message": ack_message}
    except Exception:
        log.exception("chat.delete.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_context:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_message_context(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = _payload_dict(data)
        message_id = _positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": _permissions_status(permissions.error), "error": permissions.error or "forbidden"}
            messages = await fetch_global_chat_context(db, viewer_user_id=uid, message_id=message_id)
        if not messages:
            return {"ok": False, "status": 404, "error": "message_not_found"}
        return {
            "ok": True,
            "status": 200,
            "target_message_id": message_id,
            "messages": messages,
        }
    except Exception:
        log.exception("chat.context.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}
