"""SmartReco repository layer."""

from app.repositories.base import BaseRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository

__all__ = ["BaseRepository", "ProductRepository", "UserRepository"]
