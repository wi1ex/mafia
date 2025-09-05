from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from .settings import settings
from .core.lifespan import lifespan
from .api.router import api_router
from .realtime import sio
from .realtime.sse_rooms import router as sse_rooms

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
app.include_router(sse_rooms, prefix="/sse", tags=["sse"])
app.mount("/socket.io", sio.build_sio(settings.BACKEND_CORS_ORIGINS))
