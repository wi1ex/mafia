from __future__ import annotations
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..sio import sio
from ...core.clients import get_redis
from ...db import engine
from ...utils import get_occupancies

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)


@sio.event(namespace="/rooms")
async def rooms_list(sid):
    r = get_redis()

    ids = await r.zrevrange("rooms:index", 0, 200 - 1)
    rids = [int(x) for x in ids]
    if not rids:
        return {"ok": True, "rooms": []}

    pipe = r.pipeline()
    for rid in rids:
        await pipe.hgetall(f"room:{rid}:params")
    params_list = await pipe.execute()

    occ = await get_occupancies(r, rids)
    out = []
    for rid, prm in zip(rids, params_list):
        if not prm:
            continue
        try:
            data = {
                "id": int(prm["id"]),
                "title": prm["title"],
                "user_limit": int(prm["user_limit"]),
                "is_private": prm["is_private"] in ("1", "true", "True"),
                "creator": int(prm["creator"]),
                "created_at": prm["created_at"],
                "occupancy": int(occ.get(rid, 0)),
            }
            out.append(data)
        except KeyError:
            continue

    return {"ok": True, "rooms": out}
