from __future__ import annotations
from urllib.parse import parse_qs, unquote
from socketio import AsyncServer, ASGIApp
from ..core.redis import build_redis
from ..core.security import decode_token

def build_sio(cors):
    sio = AsyncServer(async_mode="asgi", cors_allowed_origins=cors, ping_interval=20, ping_timeout=30)
    r = build_redis()

    @sio.event
    async def connect(sid, environ):
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
        uid = await r.get(f"socket:{sid}:user")
        await r.delete(f"socket:{sid}:user")
        if uid:
            await r.srem(f"user:{uid}:sockets", sid)
            if (await r.scard(f"user:{uid}:sockets")) == 0:
                await r.srem("online_users", uid)

    return ASGIApp(sio, socketio_path="socket.io")
