"""FastAPI exception handlers for consistent API error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger


logger = get_logger(__name__)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    **details: Any,
) -> JSONResponse:
    """Build the common API error response envelope."""
    error: dict[str, Any] = {"code": code, "message": message}
    error.update(details)
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": error},
    )


async def http_exception_handler(
    _request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Handle expected HTTP exceptions."""
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return _error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=detail,
    )


async def request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation failures without exposing submitted values."""
    errors = [
        {
            "location": list(error.get("loc", ())),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=errors,
    )


async def generic_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions without exposing internal details."""
    logger.exception("Unhandled application exception", exc_info=exc)
    return _error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register the centralized exception handlers on a FastAPI application."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    app.add_exception_handler(Exception, generic_exception_handler)
