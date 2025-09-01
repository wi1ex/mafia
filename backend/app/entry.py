from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import EventSourceResponse
from socketio import AsyncServer, ASGIApp

from .settings import settings
from .api.router import api_router
from .core.logging import configure_logging  # <— фикс импорта

configure_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/sse/events")
async def sse_events():
    async def gen():
        yield {"event": "health", "data": "ok"}
    return EventSourceResponse(gen())

sio = AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.BACKEND_CORS_ORIGINS,
    ping_interval=20,
    ping_timeout=30,
)
sio_app = ASGIApp(sio, socketio_path="socket.io")  # по умолчанию так
app.mount("/ws-sio", sio_app)

@sio.event
async def connect(sid, environ): pass

@sio.event
async def disconnect(sid): pass

asgi = app
