from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.router import api_router
from .realtime.ws_rooms  import router as ws_rooms_router
from .core.lifespan import lifespan
from .settings import settings

def build_app() -> FastAPI:
    main_app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

    main_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    main_app.include_router(api_router, prefix="/api")
    main_app.include_router(ws_rooms_router, prefix="/ws")

    return main_app

app = build_app()
