"""FastAPI application bootstrap for SmartReco."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.lifecycle import lifespan
from app.core.logging import configure_logging
from app.core.metadata import APP_DESCRIPTION, APP_TITLE, OPENAPI_TAGS
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.timing import TimingMiddleware
from app.utils.exceptions import register_exception_handlers


configure_logging()

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=settings.app_version,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url=settings.openapi_url,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    debug=settings.debug,
)

register_exception_handlers(app)

app.add_middleware(TimingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(api_router)

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
