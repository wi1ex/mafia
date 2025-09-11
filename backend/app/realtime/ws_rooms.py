from __future__ import annotations
import json
import asyncio
from contextlib import suppress
from typing import Set
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.clients import get_redis
from ..settings import settings


router = APIRouter()


CLIENTS: Set[WebSocket] = set()
_stream_task: asyncio.Task | None = None
_lock = asyncio.Lock()
log = structlog.get_logger()


async def _snapshot() -> list[dict]:
    r = get_redis()
    ids = await r.smembers("rooms:index")
    result: list[dict] = []
    for sid in sorted((int(x) for x in ids), reverse=True):
        data = await r.hgetall(f"room:{sid}:params")
        if not data:
            continue
        result.append({
            "id": int(data["id"]),
            "title": data["title"],
            "user_limit": int(data["user_limit"]),
            "is_private": bool(int(data["is_private"])),
            "created_by_user_id": int(data["created_by_user_id"]),
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "occupancy": int(data["occupancy"]),
        })
    return result


async def _broadcast(payload: dict) -> None:
    if not CLIENTS:
        return
    msg = json.dumps(payload)
    dead: list[WebSocket] = []
    for ws in CLIENTS:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    if dead:
        for ws in dead:
            CLIENTS.discard(ws)
        log.warning("ws.broadcast.dropped", dropped=len(dead), alive=len(CLIENTS))
    else:
        log.debug("ws.broadcast.sent", receivers=len(CLIENTS), type=payload.get("type"))


async def _stream_loop() -> None:
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("rooms:events")
    log.info("ws.stream.started")
    try:
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue
            data = msg.get("data")
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8", errors="ignore")
            try:
                payload = json.loads(data)
            except Exception:
                log.warning("ws.stream.bad_message")
                continue
            try:
                await _broadcast(payload)
            except Exception:
                log.exception("ws.stream.broadcast_error")
    except Exception:
        log.exception("ws.stream.error")
        raise
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe("rooms:events")
        with suppress(Exception):
            await pubsub.aclose()
        log.info("ws.stream.stopped")


async def _ensure_stream() -> None:
    global _stream_task
    if _stream_task and not _stream_task.done():
        return
    async with _lock:
        if _stream_task and not _stream_task.done():
            return
        _stream_task = asyncio.create_task(_stream_loop())


@router.websocket("/rooms")
async def rooms_ws(ws: WebSocket):
    origin = ws.headers.get("sec-websocket-origin") or ws.headers.get("origin")
    expected = f"https://{settings.DOMAIN}"
    if origin != expected:
        log.warning("ws.reject.origin", origin=origin, expected=expected)
        with suppress(Exception):
            await ws.close(code=1008)
        return

    await ws.accept()
    await _ensure_stream()
    CLIENTS.add(ws)
    peer = f"{getattr(ws.client, 'host', '-') }:{getattr(ws.client, 'port', '-')}" if ws.client else "-"
    log.info("ws.client.connected", peer=peer, clients=len(CLIENTS))
    try:
        await ws.send_text(json.dumps({"type": "rooms_snapshot", "payload": await _snapshot()}))
        while True:
            with suppress(Exception):
                await ws.receive_text()
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        log.info("ws.client.disconnected", peer=peer)
    except Exception:
        log.exception("ws.client.error", peer=peer)
        with suppress(Exception):
            await ws.close(code=1011)
    finally:
        CLIENTS.discard(ws)
        log.info("ws.client.removed", clients=len(CLIENTS))
