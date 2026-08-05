"""FastAPI application bootstrap for SmartReco."""

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.metadata import APP_DESCRIPTION, APP_TITLE, OPENAPI_TAGS


settings = get_settings()

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=settings.app_version,
    docs_url=settings.docs_url,
    redoc_url=settings.redoc_url,
    openapi_url=settings.openapi_url,
    openapi_tags=OPENAPI_TAGS,
    debug=settings.debug,
)
