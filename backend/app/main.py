from __future__ import annotations
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from .api.router import api_router
from .core.handlers import setup_exception_handlers
from .core.lifespan import lifespan
from .core.middleware import LoggingMiddleware, LastLoginTouchMiddleware
from .realtime.sio import sio
from .core.settings import settings


def build_fastapi() -> FastAPI:
    main_app = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    main_app.add_middleware(LoggingMiddleware)
    main_app.add_middleware(LastLoginTouchMiddleware)

    main_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    setup_exception_handlers(main_app)

    main_app.include_router(api_router, prefix="/api")

    return main_app


_fastapi = build_fastapi()

app = socketio.ASGIApp(sio, other_asgi_app=_fastapi, socketio_path="ws/socket.io")
