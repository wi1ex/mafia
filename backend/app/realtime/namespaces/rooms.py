from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from ...db import engine
from ...models.room import Room
from ..sio import sio
from ...core.clients import get_redis
from ...utils import serialize_room, get_occupancies

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)

@sio.event(namespace="/rooms")
async def rooms_list(sid):
    r = get_redis()
    async with _sessionmaker() as s:
        rooms = (await s.execute(select(Room))).scalars().all()

    rids = [rm.id for rm in rooms]
    occ = await get_occupancies(r, rids)
    out = [serialize_room(rm, occupancy=occ.get(rm.id, 0)) for rm in rooms]
    return {"ok": True, "rooms": out}
