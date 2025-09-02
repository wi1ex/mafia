from asyncio import sleep
from fastapi import APIRouter
from starlette.responses import EventSourceResponse
import json

router = APIRouter()

@router.get("/events")
async def events():
    async def gen():
        yield {"event": "health", "data": json.dumps({"status":"ok"})}
        while True:
            yield ": keepalive\n\n"
            await sleep(15)
    return EventSourceResponse(gen(), media_type="text/event-stream")
