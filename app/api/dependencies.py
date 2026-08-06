"""Shared FastAPI dependency exports."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.services.product import ProductService
from app.services.user import UserService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service for the current request transaction."""
    return UserService(UserRepository(db))


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    """Build a product service for the current request transaction."""
    return ProductService(ProductRepository(db))


__all__ = ["get_db", "get_product_service", "get_user_service"]
