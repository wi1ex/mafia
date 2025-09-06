from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from .settings import settings
from .api.router import api_router
from .realtime import sse_rooms, sio
from .core.lifespan import lifespan

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(sse_rooms.router, prefix="/sse", tags=["sse"])
app.mount("/socket.io", sio.build_sio(settings.BACKEND_CORS_ORIGINS))
