import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import AppError

logger = logging.getLogger(__name__)

_HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
}


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "correlationId": getattr(request.state, "correlation_id", None),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error})


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(request, exc.status_code, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]
    return _error_response(request, 422, "validation_error", "La petición no es válida", details)


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    return _error_response(request, exc.status_code, code, str(exc.detail))


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_error",
        exc_info=exc,
        extra={"path": request.url.path, "method": request.method},
    )
    return _error_response(request, 500, "internal_error", "Error interno del servidor")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
