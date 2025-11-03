from __future__ import annotations
import structlog
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from fastapi.responses import JSONResponse
from ..schemas.common import ErrorOut


def setup_exception_handlers(app: FastAPI) -> None:
    log = structlog.get_logger()

    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, exc: HTTPException):
        log.warning("http_exception", status=exc.status_code, detail=exc.detail)
        return JSONResponse(ErrorOut(detail=str(exc.detail)).model_dump(), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_exception")
        return JSONResponse(ErrorOut(detail="internal error").model_dump(), status_code=500)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        return JSONResponse(ErrorOut(detail="validation_error").model_dump(), status_code=HTTP_422_UNPROCESSABLE_ENTITY)
