from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from ...db import engine
from ...models.room import Room
from ..sio import sio
from ...core.clients import get_redis
from ...utils import serialize_room

_sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)

@sio.event(namespace="/rooms")
async def rooms_list(sid):
    r = get_redis()
    async with _sessionmaker() as s:
        rooms = (await s.execute(select(Room))).scalars().all()
    pipe = r.pipeline()
    for rm in rooms:
        await pipe.scard(f"room:{rm.id}:members")
    occs = await pipe.execute()
    out = [serialize_room(rm, occupancy=int(occ or 0)) for rm, occ in zip(rooms, occs)]
    return {"ok": True, "rooms": out}
