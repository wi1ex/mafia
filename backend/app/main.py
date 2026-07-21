from __future__ import annotations
from pathlib import Path
import socketio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .api.router import api_router
from .core.handlers import setup_exception_handlers
from .core.lifespan import lifespan
from .core.middleware import LoggingMiddleware, LastLoginTouchMiddleware, SecurityHeadersMiddleware
from .realtime.sio import sio, register_namespaces
from .core.settings import settings


LEGAL_FILES_DIR = Path(__file__).resolve().parent / "static" / "files"
PUBLIC_LEGAL_FILES = {
    "user-agreement.pdf": "Пользовательское соглашение",
    "privacy-policy.pdf": "Политика обработки персональных данных",
}


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

    @main_app.get("/files/{filename}", include_in_schema=False)
    async def public_legal_file(filename: str) -> FileResponse:
        download_name = PUBLIC_LEGAL_FILES.get(filename)
        if not download_name:
            raise HTTPException(status_code=404, detail="not_found")

        path = LEGAL_FILES_DIR / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="not_found")

        return FileResponse(
            path,
            media_type="application/pdf",
            filename=download_name,
            content_disposition_type="inline",
            headers={"Cache-Control": "no-store"},
        )

    return main_app


_fastapi = build_fastapi()
register_namespaces()

app = socketio.ASGIApp(sio, other_asgi_app=_fastapi, socketio_path="ws/socket.io")
