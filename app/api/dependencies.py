"""Shared FastAPI dependency exports."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.user import UserRepository
from app.services.user import UserService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service for the current request transaction."""
    return UserService(UserRepository(db))


__all__ = ["get_db", "get_user_service"]
