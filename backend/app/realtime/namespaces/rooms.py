from __future__ import annotations
import structlog
from ..sio import sio
from ...core.clients import get_redis

log = structlog.get_logger()


@sio.event(namespace="/rooms")
async def rooms_list(sid):
    try:
        r = get_redis()
        rids = list(map(int, await r.zrevrange("rooms:index", 0, 99)))
        if not rids:
            return {"ok": True, "rooms": []}

        fields = ("id", "title", "user_limit", "creator", "created_at")
        async with r.pipeline() as p:
            for rid in rids:
                await p.hmget(f"room:{rid}:params", *fields)
            for rid in rids:
                await p.scard(f"room:{rid}:members")
            res = await p.execute()

        rows, occ_vals = res[:len(rids)], res[len(rids):]
        occ = {rid: int(v or 0) for rid, v in zip(rids, occ_vals)}
        rooms = [{"id": int(_id), "title": title, "user_limit": int(user_limit),
                  "creator": int(creator), "created_at": created_at, "occupancy": occ.get(rid, 0)}
                 for rid, (_id, title, user_limit, creator, created_at) in zip(rids, rows)
                 if None not in (_id, title, user_limit, creator, created_at)]
        return {"ok": True, "rooms": rooms}

    except Exception:
        log.exception("rooms.list.error", sid=sid)
        return {"ok": True, "rooms": []}
