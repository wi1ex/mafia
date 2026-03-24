from __future__ import annotations
from contextlib import suppress
from uuid import UUID
import structlog
from ..sio import sio
from ..utils import payload_dict, permissions_status, positive_int, public_reactions, validate_auth
from ...core.db import SessionLocal
from ...core.logging import log_action
from ...security.decorators import rate_limited_sio
from ...services.global_chat import (
    GLOBAL_CHAT_REACTIONS_ALLOWLIST,
    GLOBAL_CHAT_ROOM,
    build_deleted_global_chat_message_preview,
    build_global_chat_message_payload,
    create_global_chat_message,
    delete_global_chat_message,
    fetch_global_chat_reaction_participants,
    fetch_global_chat_context,
    fetch_global_chat_page,
    global_chat_send_error,
    global_chat_open_user_room,
    get_global_chat_message,
    permissions_payload,
    purge_global_chat_message,
    resolve_global_chat_permissions,
    toggle_global_chat_reaction,
    validate_global_chat_send_input,
)

log = structlog.get_logger()


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
    joined_global_room = False
    joined_user_room = False
    uid = 0
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = payload_dict(data)
        limit = positive_int(payload.get("limit"))

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {
                    "ok": False,
                    "status": permissions_status(permissions.error),
                    "error": permissions.error or "forbidden",
                    "permissions": permissions_payload(permissions),
                }

        await sio.enter_room(sid, GLOBAL_CHAT_ROOM, namespace="/chat")
        joined_global_room = True
        await sio.enter_room(sid, global_chat_open_user_room(uid), namespace="/chat")
        joined_user_room = True
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
        if uid > 0:
            if joined_global_room:
                with suppress(Exception):
                    await sio.leave_room(sid, GLOBAL_CHAT_ROOM, namespace="/chat")
            if joined_user_room:
                with suppress(Exception):
                    await sio.leave_room(sid, global_chat_open_user_room(uid), namespace="/chat")
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
                "status": permissions_status(permissions.error),
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
        payload = payload_dict(data)
        before_raw = payload.get("before_id") if "before_id" in payload else None
        before_id = positive_int(before_raw)
        limit = positive_int(payload.get("limit"))

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

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
        payload = payload_dict(data)
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

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

            if not permissions.can_send:
                return {"ok": False, "status": 403, "error": global_chat_send_error(permissions)}

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
        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        emoji = str(payload.get("emoji") or "")
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open or not permissions.can_react:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

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
                    "reactions": public_reactions(public_message["reactions"]),
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


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_reaction_participants:{uid or 'nouid'}", limit=10, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_reaction_participants(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {
                    "ok": False,
                    "status": permissions_status(permissions.error),
                    "error": permissions.error or "forbidden",
                }

            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}

            if message.deleted_at is not None:
                return {"ok": False, "status": 409, "error": "message_deleted"}

            participants = await fetch_global_chat_reaction_participants(db, message_id=message_id)

        return {
            "ok": True,
            "status": 200,
            "message_id": message_id,
            "participants": participants,
        }

    except Exception:
        log.exception("chat.reaction_participants.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_delete:{uid or 'nouid'}", limit=10, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_delete(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        role = str(sess.get("role") or "").strip().lower()
        actor_username = str(sess.get("username") or f"user{uid}")
        is_admin = role == "admin"
        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open and not is_admin:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

            if not permissions.can_delete_own and not is_admin:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}

            if not is_admin and int(message.user_id) != uid:
                return {"ok": False, "status": 403, "error": "forbidden"}

            if message.deleted_at is not None:
                return {"ok": False, "status": 409, "error": "already_deleted"}

            message_author_id = int(message.user_id)
            message_author_username = ""
            message_payload = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            if message_payload is not None:
                author = message_payload.get("author") or {}
                message_author_username = str(author.get("username") or "").strip()
            is_self_delete = message_author_id == uid
            had_text = int(bool(str(message.text or "").strip()))
            has_image = int(bool(message.image_object_key))
            reply_to_message_id = positive_int(message.reply_to_message_id)

            await delete_global_chat_message(db, message=message, actor_user_id=uid)

            try:
                details = f"Удаление сообщения чата message_id={message_id} author_user_id={message_author_id}"
                if message_author_username:
                    details += f" author_username={message_author_username}"
                details += f" had_text={had_text} has_image={has_image}"
                if reply_to_message_id > 0:
                    details += f" reply_to_message_id={reply_to_message_id}"
                if not is_self_delete:
                    details += f" actor_user_id={uid}"
                    if actor_username:
                        details += f" actor_username={actor_username}"
                    if role:
                        details += f" actor_role={role}"
                await log_action(
                    db,
                    user_id=uid,
                    username=actor_username,
                    action="chat_message_deleted_self" if is_self_delete else "chat_message_deleted_admin",
                    details=details,
                )
            except Exception:
                log.exception("chat.delete.log_failed", sid=sid, uid=uid, message_id=message_id)

            ack_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            public_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=None)

        if public_message is not None:
            await sio.emit("chat_message_deleted", public_message, room=GLOBAL_CHAT_ROOM, namespace="/chat")

        return {"ok": True, "status": 200, "message": ack_message}

    except Exception:
        log.exception("chat.delete.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_deleted_preview:{uid or 'nouid'}", limit=10, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_deleted_message_preview(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        role = str(sess.get("role") or "").strip().lower()
        if role != "admin":
            return {"ok": False, "status": 403, "error": "forbidden"}

        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}

            if message.deleted_at is None:
                return {"ok": False, "status": 409, "error": "not_deleted"}

            preview = await build_deleted_global_chat_message_preview(db, message=message)

        return {"ok": True, "status": 200, "preview": preview}

    except Exception:
        log.exception("chat.deleted_preview.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_purge:{uid or 'nouid'}", limit=5, window_s=10, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_message_purge(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        role = str(sess.get("role") or "").strip().lower()
        actor_username = str(sess.get("username") or f"user{uid}")
        if role != "admin":
            return {"ok": False, "status": 403, "error": "forbidden"}

        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            message = await get_global_chat_message(db, message_id)
            if message is None:
                return {"ok": False, "status": 404, "error": "message_not_found"}

            if message.deleted_at is None:
                return {"ok": False, "status": 409, "error": "not_deleted"}

            message_author_id = int(message.user_id)
            message_author_username = ""
            message_payload = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            if message_payload is not None:
                author = message_payload.get("author") or {}
                message_author_username = str(author.get("username") or "").strip()

            had_text = int(bool(str(message.text or "").strip()))
            has_image = int(bool(message.image_object_key))
            if not had_text and not has_image:
                return {"ok": False, "status": 409, "error": "already_purged"}

            await purge_global_chat_message(db, message=message)

            try:
                details = f"Окончательное удаление сообщения чата message_id={message_id} author_user_id={message_author_id}"
                if message_author_username:
                    details += f" author_username={message_author_username}"
                details += f" actor_user_id={uid}"
                if actor_username:
                    details += f" actor_username={actor_username}"
                details += f" actor_role={role} had_text={had_text} has_image={has_image}"
                await log_action(
                    db,
                    user_id=uid,
                    username=actor_username,
                    action="chat_message_purged_admin",
                    details=details,
                )
            except Exception:
                log.exception("chat.purge.log_failed", sid=sid, uid=uid, message_id=message_id)

            ack_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=uid)
            public_message = await build_global_chat_message_payload(db, message_id=message_id, viewer_user_id=None)

        if public_message is not None:
            await sio.emit("chat_message_deleted", public_message, room=GLOBAL_CHAT_ROOM, namespace="/chat")

        return {"ok": True, "status": 200, "message": ack_message}

    except Exception:
        log.exception("chat.purge.error", sid=sid)
        return {"ok": False, "status": 500, "error": "internal"}


@rate_limited_sio(lambda *, uid=None, **__: f"rl:sio:chat_context:{uid or 'nouid'}", limit=5, window_s=1, session_ns="/chat")
@sio.event(namespace="/chat")
async def chat_message_context(sid, data):
    try:
        sess = await sio.get_session(sid, namespace="/chat")
        uid = int(sess.get("uid") or 0)
        payload = payload_dict(data)
        message_id = positive_int(payload.get("message_id"))
        if message_id <= 0:
            return {"ok": False, "status": 422, "error": "bad_message_id"}

        async with SessionLocal() as db:
            permissions = await resolve_global_chat_permissions(db, uid)
            if not permissions.can_open:
                return {"ok": False, "status": permissions_status(permissions.error), "error": permissions.error or "forbidden"}

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
