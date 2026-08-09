"""Shared FastAPI dependency exports."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.event import EventRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.services.event_service import EventService
from app.services.product import ProductService
from app.services.user import UserService
from app.services.vector_service import ProductVectorService


bearer_scheme = HTTPBearer(auto_error=False)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service for the current request transaction."""
    return UserService(UserRepository(db))


def get_product_vector_service() -> ProductVectorService:
    """Build Product vector indexing dependencies from configuration."""
    return ProductVectorService.from_settings()


def get_product_service(
    db: Session = Depends(get_db),
    vector_service: ProductVectorService = Depends(get_product_vector_service),
) -> ProductService:
    """Build a product service for the current request transaction."""
    return ProductService(ProductRepository(db), vector_service)


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    """Build an event service for the current request transaction."""
    return EventService(EventRepository(db))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve an active user from a valid bearer access token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


__all__ = [
    "get_current_user",
    "get_db",
    "get_event_service",
    "get_product_service",
    "get_product_vector_service",
    "get_user_service",
]
