"""Request timing middleware for the SmartReco API."""

from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TimingMiddleware(BaseHTTPMiddleware):
    """Add request processing time to each response."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Measure request processing time and set the response header."""
        start_time = perf_counter()
        response = await call_next(request)
        elapsed = perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{elapsed:.6f}"
        return response
