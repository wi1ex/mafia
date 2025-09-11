from __future__ import annotations
import structlog
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


def setup_exception_handlers(app: FastAPI) -> None:
    log = structlog.get_logger()

    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, exc: HTTPException):
        log.warning("http_exception", status=exc.status_code, detail=exc.detail)
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_exception")
        return JSONResponse({"detail": "internal error"}, status_code=500)
