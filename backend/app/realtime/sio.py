from __future__ import annotations
import asyncio
from urllib.parse import parse_qs, unquote
from socketio import AsyncServer, ASGIApp
from ..core.clients import get_redis
from ..core.security import decode_token

def build_sio(cors):
    sio = AsyncServer(async_mode="asgi", cors_allowed_origins=cors, ping_interval=20, ping_timeout=30)

    async def ensure_redis():
        # Ждём, пока lifespan инициализирует клиентов
        while True:
            try:
                r = get_redis()
                await r.ping()
                return r
            except Exception:
                await asyncio.sleep(0.5)

    @sio.event
    async def connect(sid, environ):
        r = await ensure_redis()

        # Ожидаем ?token=Bearer%20<jwt> или ?token=<jwt>
        qs = parse_qs(environ.get("QUERY_STRING") or "")
        raw = (qs.get("token") or [None])[0]
        if not raw:
            return False
        tok = unquote(raw)
        if tok.lower().startswith("bearer "):
            tok = tok[7:].strip()

        try:
            payload = decode_token(tok)
            uid = payload.get("sub")
            sid_claim = payload.get("sid")
            if not uid or not sid_claim:
                return False
            # single-session: текущая сессия пользователя должна совпадать
            current_sid = await r.get(f"user:{uid}:session")
            if current_sid != sid_claim:
                return False
        except Exception:
            return False

        # учёт онлайна
        await r.sadd("online_users", uid)
        await r.sadd(f"user:{uid}:sockets", sid)
        await r.set(f"socket:{sid}:user", uid, ex=86400)
        return True

    @sio.event
    async def disconnect(sid):
        r = await ensure_redis()
        uid = await r.get(f"socket:{sid}:user")
        await r.delete(f"socket:{sid}:user")
        if uid:
            await r.srem(f"user:{uid}:sockets", sid)
            if (await r.scard(f"user:{uid}:sockets")) == 0:
                await r.srem("online_users", uid)

    async def _kick_subscriber():
        r = await ensure_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe("sio:kick")
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                uid = msg.get("data")
                if isinstance(uid, bytes):
                    uid = uid.decode()
                # разрываем все сокеты пользователя
                sids = await r.smembers(f"user:{uid}:sockets")
                for s in sids:
                    try:
                        await sio.disconnect(s)
                    except Exception:
                        pass
        finally:
            await pubsub.unsubscribe("sio:kick")
            await pubsub.close()

    asyncio.create_task(_kick_subscriber())
    return ASGIApp(sio, socketio_path="socket.io")
