"""Application health endpoint."""

from fastapi import APIRouter

from app.core.config import settings



router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", status_code=200)
async def health_check() -> dict[str, str]:
    """Return the current application health and metadata."""
    return {
        "status": "healthy",
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
