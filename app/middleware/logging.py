"""Request logging middleware for the SmartReco API."""

from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger


logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one summary entry after each completed request."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Log method, path, status, and processing time for a request."""
        start_time = perf_counter()
        try:
            response = await call_next(request)
        finally:
            process_time = perf_counter() - start_time

        logger.info(
            "request_completed method=%s path=%s status_code=%d process_time=%.6f",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )

        return response
