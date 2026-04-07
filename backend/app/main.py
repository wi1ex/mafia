from __future__ import annotations
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.router import api_router
from .core.handlers import setup_exception_handlers
from .core.lifespan import lifespan
from .core.middleware import LoggingMiddleware, LastLoginTouchMiddleware, SecurityHeadersMiddleware
from .realtime.sio import sio, register_namespaces
from .core.settings import settings


def build_fastapi() -> FastAPI:
    main_app = FastAPI(
        title=settings.PROJECT_NAME,
        lifespan=lifespan,
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
    main_app.add_middleware(SecurityHeadersMiddleware)
    setup_exception_handlers(main_app)

    main_app.include_router(api_router, prefix="/api")

    return main_app


_fastapi = build_fastapi()
register_namespaces()

app = socketio.ASGIApp(sio, other_asgi_app=_fastapi, socketio_path="ws/socket.io")
