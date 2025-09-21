from __future__ import annotations
import structlog
from ..sio import sio
from ...core.clients import get_redis
from ...utils import get_occupancies

log = structlog.get_logger()


@sio.event(namespace="/rooms")
async def rooms_list(sid):
    try:
        r = get_redis()
        ids = await r.zrevrange("rooms:index", 0, 200 - 1)
        rids = [int(x) for x in ids]
        if not rids:
            return {"ok": True, "rooms": []}

        fields = ("id", "title", "user_limit", "is_private", "creator", "created_at")
        pipe = r.pipeline()
        for rid in rids:
            await pipe.hmget(f"room:{rid}:params", *fields)
        rows = await pipe.execute()
        occ = await get_occupancies(r, rids)

        out = []
        for rid, vals in zip(rids, rows):
            if not vals or any(v is None for v in vals):
                continue
            _id, title, user_limit, is_private, creator, created_at = vals
            out.append({
                "id": int(_id), "title": title,
                "user_limit": int(user_limit),
                "is_private": str(is_private) in ("1", "true", "True"),
                "creator": int(creator),
                "created_at": created_at,
                "occupancy": int(occ.get(rid, 0)),
            })

        return {"ok": True, "rooms": out}

    except Exception:
        log.exception("rooms.list.error", sid=sid)
        return {"ok": True, "rooms": []}
