from __future__ import annotations
import asyncio
import json
import time
from contextlib import suppress
from typing import Dict, Any
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path, Depends
from starlette.websockets import WebSocketState
from ..core.clients import get_redis
from ..services.sessions import get_current_user
from ..models.user import User


router = APIRouter()
log = structlog.get_logger()


async def _room_snapshot(r, room_id: int) -> Dict[str, Dict[str, str]]:
    members = await r.smembers(f"room:{room_id}:members")
    out: Dict[str, Dict[str, str]] = {}
    for uid_b in members or []:
        uid = uid_b.decode() if isinstance(uid_b, (bytes, bytearray)) else str(uid_b)
        st = await r.hgetall(f"room:{room_id}:user:{uid}:state")
        out[uid] = {
            (k.decode() if isinstance(k, (bytes, bytearray)) else k):
            (v.decode() if isinstance(v, (bytes, bytearray)) else v)
            for k, v in (st or {}).items()
        }
    return out


async def _broadcast_room(r, room_id: int, payload: Dict[str, Any]) -> None:
    await r.publish(f"room:{room_id}:events", json.dumps(payload))


async def _broadcast_rooms(r, payload: Dict[str, Any]) -> None:
    await r.publish("rooms:events", json.dumps(payload))


async def _apply_state(r, room_id: int, user_id: int, data: Dict[str, Any]) -> Dict[str, str]:
    norm = {k: "1" if bool(v) else "0" for k, v in data.items()
            if k in {"mic", "cam", "speakers", "visibility"}}
    if not norm:
        return {}
    await r.hset(f"room:{room_id}:user:{user_id}:state", mapping=norm)
    await r.hset(f"user:{user_id}:last_state", mapping=norm)
    return norm


async def _force_leave(r, room_id: int, user_id: int) -> None:
    await r.srem(f"room:{room_id}:members", user_id)
    await r.delete(f"room:{room_id}:member:{user_id}")
    await r.delete(f"room:{room_id}:user:{user_id}:state")
    occ = int(await r.scard(f"room:{room_id}:members") or 0)
    await _broadcast_rooms(r, {"type": "occupancy", "payload": {"id": room_id, "occupancy": occ}})
    await _broadcast_room(r, room_id, {"type": "member_left", "payload": {"user_id": user_id, "ts": int(time.time())}})


@router.websocket("/room/{room_id}")
async def room_ws(ws: WebSocket, room_id: int = Path(..., ge=1), user: User = Depends(get_current_user)):
    await ws.accept()
    r = await get_redis()
    uid = int(user.id)
    now = int(time.time())

    await ws.send_text(json.dumps({"type": "snapshot", "payload": await _room_snapshot(r, room_id), "ts": now}))

    pub = r.pubsub()
    await pub.subscribe(f"room:{room_id}:events")

    async def heartbeats():
        while ws.application_state == WebSocketState.CONNECTED:
            with suppress(Exception):
                await r.set(f"room:{room_id}:member:{uid}", str(int(time.time())))
            await asyncio.sleep(15)

    hb_task = asyncio.create_task(heartbeats())

    async def consume_incoming():
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            seq = msg.get("seq")
            ts = int(time.time())
            if mtype == "state":
                payload = msg.get("payload") or {}
                applied = await _apply_state(r, room_id, uid, payload)
                if applied:
                    evt = {"type": "state_changed", "payload": {"user_id": uid, **applied}, "origin": uid, "ts": ts}
                    await _broadcast_room(r, room_id, evt)
                await ws.send_text(json.dumps({"type": "state_ack", "seq": seq, "ts": ts}))
            elif mtype == "goodbye":
                await _force_leave(r, room_id, uid)
                await ws.send_text(json.dumps({"type": "goodbye_ack", "seq": seq, "ts": ts}))

    incoming_task = asyncio.create_task(consume_incoming())

    try:
        while True:
            message = await pub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode()
                await ws.send_text(data)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws.room.error", room_id=room_id, user_id=uid)
    finally:
        with suppress(Exception):
            await pub.unsubscribe(f"room:{room_id}:events")
            await pub.close()
        with suppress(Exception):
            hb_task.cancel()
        with suppress(Exception):
            incoming_task.cancel()
