"""Shared FastAPI dependency exports."""

from app.database.session import get_db


__all__ = ["get_db"]
