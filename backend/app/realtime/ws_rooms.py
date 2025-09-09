from __future__ import annotations
import json
import asyncio
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.clients import get_redis

router = APIRouter()

CLIENTS: Set[WebSocket] = set()
_stream_task: asyncio.Task | None = None
_lock = asyncio.Lock()


async def _snapshot() -> list[dict]:
    r = get_redis()
    ids = sorted(int(i) for i in await r.smembers("rooms:index"))
    if not ids:
        return []
    p = r.pipeline()
    for rid in ids:
        await p.hgetall(f"room:{rid}:params")
        await p.scard(f"room:{rid}:members")
    raw = await p.execute()
    out = []
    for i, rid in enumerate(ids):
        params = raw[2 * i] or {}
        occ = int(raw[2 * i + 1] or 0)
        out.append({
            "id": rid,
            "title": params.get("title", ""),
            "user_limit": int(params.get("user_limit", 0)),
            "is_private": bool(int(params.get("is_private", 0))),
            "created_by_user_id": int(params.get("created_by", 0)),
            "created_at": params.get("created_at", ""),
            "updated_at": params.get("updated_at", params.get("created_at", "")),
            "occupancy": occ,
        })
    return out


async def _broadcast(txt: str) -> None:
    dead = []
    for ws in list(CLIENTS):
        try:
            await ws.send_text(txt)
        except Exception:
            dead.append(ws)
    for ws in dead: CLIENTS.discard(ws)


async def _stream_loop() -> None:
    r = get_redis()
    ps = r.pubsub()
    await ps.subscribe("rooms:events")
    try:
        while True:
            m = await ps.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if m and m.get("type") == "message":
                d = m["data"]
                txt = d if isinstance(d, str) else d.decode()
                await _broadcast(txt)
            else:
                await asyncio.sleep(0.2)
    finally:
        await ps.unsubscribe("rooms:events")
        await ps.close()


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
    await ws.accept()
    await _ensure_stream()
    CLIENTS.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "rooms_snapshot", "payload": await _snapshot()}))
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    finally:
        CLIENTS.discard(ws)
