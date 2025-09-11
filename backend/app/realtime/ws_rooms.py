from __future__ import annotations
import json
import asyncio
from contextlib import suppress
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.clients import get_redis


router = APIRouter()


CLIENTS: Set[WebSocket] = set()
_stream_task: asyncio.Task | None = None


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
    dead: list[WebSocket] = []
    msg = json.dumps(payload)
    for ws in CLIENTS:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        CLIENTS.discard(ws)


async def _stream_loop() -> None:
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("rooms:events")
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
                continue
            await _broadcast(payload)
    finally:
        with suppress(Exception):
            await pubsub.unsubscribe("rooms:events")
        with suppress(Exception):
            await pubsub.aclose()


async def _ensure_stream() -> None:
    global _stream_task
    if _stream_task and not _stream_task.done():
        return
    async with asyncio.Lock():
        if _stream_task and not _stream_task.done():
            return
        _stream_task = asyncio.create_task(_stream_loop())


@router.websocket("/rooms")
async def rooms_ws(ws: WebSocket):
    await ws.accept()
    await _ensure_stream()
    CLIENTS.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "rooms_snapshot", "payload": await _snapshot()}))
        while True:
            with suppress(Exception):
                await ws.receive_text()
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(ws)
