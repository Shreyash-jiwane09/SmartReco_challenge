"""Repository operations for products."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Provide persistence operations for products."""

    def __init__(self, session: Session) -> None:
        super().__init__(Product, session)
