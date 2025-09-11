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
log = structlog.get_logger()


CLIENTS: Set[WebSocket] = set()
_stream_task: asyncio.Task | None = None
_lock = asyncio.Lock()


def _to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _to_bool(v) -> bool:
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "on"}


async def _snapshot() -> list[dict]:
    r = get_redis()
    ids = await r.smembers("rooms:index")
    result: list[dict] = []
    for sid in sorted((_to_int(x, 0) for x in ids), reverse=True):
        if not sid:
            continue
        data = await r.hgetall(f"room:{sid}:params")
        if not data:
            log.warning("ws.snapshot.missing_params", room_id=sid)
            continue

        rid = _to_int(data.get("id", sid), sid)
        try:
            result.append({
                "id": rid,
                "title": data.get("title", ""),
                "user_limit": _to_int(data.get("user_limit"), 0),
                "is_private": _to_bool(data.get("is_private", 0)),
                "created_by_user_id": _to_int(data.get("created_by_user_id"), 0),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "occupancy": _to_int(data.get("occupancy"), 0),
            })
        except Exception as e:
            log.warning("ws.snapshot.bad_item", room_id=sid, err=str(e), data_keys=list(data.keys()))
            continue
    return result


async def _broadcast(payload: dict) -> None:
    dead: list[WebSocket] = []
    msg = json.dumps(payload)
    for ws in CLIENTS:
        try:
            await ws.send_text(msg)
        except Exception as e:
            dead.append(ws)
            log.error("ws.broadcast.error", err=str(e))
    for ws in dead:
        CLIENTS.discard(ws)


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
                log.warning("ws.stream.bad_json")
                continue
            await _broadcast(payload)
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
    if origin != f"https://{settings.DOMAIN}":
        with suppress(Exception):
            await ws.close(code=1008)
        return

    await ws.accept()
    await _ensure_stream()
    CLIENTS.add(ws)
    log.info("ws.client.connected", peer=f"{ws.client.host}:{ws.client.port}", clients=len(CLIENTS))
    try:
        await ws.send_text(json.dumps({"type": "rooms_snapshot", "payload": await _snapshot()}))
        while True:
            with suppress(Exception):
                await ws.receive_text()
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("ws.client.error", peer=f"{ws.client.host}:{ws.client.port}", err=str(e))
    finally:
        CLIENTS.discard(ws)
        log.info("ws.client.removed", clients=len(CLIENTS))
