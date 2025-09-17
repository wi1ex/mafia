from __future__ import annotations
from ..sio import sio

@sio.event(namespace="/rooms")
async def connect(sid, environ, auth):
    return
