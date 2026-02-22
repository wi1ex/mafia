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
        status = int(exc.status_code or 500)
        if 400 <= status < 500 and status != 429:
            log.info("http_exception", status=status, detail=exc.detail)
        elif status == 429:
            log.warning("http_exception", status=status, detail=exc.detail)
        else:
            log.error("http_exception", status=status, detail=exc.detail)

        raw_detail = exc.detail
        if isinstance(raw_detail, str):
            detail = raw_detail
        elif isinstance(raw_detail, dict):
            detail = {str(k): v for k, v in raw_detail.items()}
        else:
            detail = str(raw_detail)

        return JSONResponse(ErrorOut(detail=detail).model_dump(), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled_exception")
        return JSONResponse(ErrorOut(detail="internal error").model_dump(), status_code=500)

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        return JSONResponse(ErrorOut(detail="validation_error").model_dump(), status_code=HTTP_422_UNPROCESSABLE_ENTITY)
