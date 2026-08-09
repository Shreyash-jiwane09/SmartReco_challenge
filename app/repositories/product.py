"""Repository operations for products."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Provide persistence operations for products."""

    def __init__(self, session: Session) -> None:
        super().__init__(Product, session)

    def list_active(self) -> list[Product]:
        """Return active catalog products in a stable display order."""
        statement = (
            select(Product)
            .where(Product.is_active.is_(True))
            .order_by(Product.title.asc())
        )
        return list(self.session.execute(statement).scalars().all())

    def search_active(self, query: str) -> list[Product]:
        """Search active catalog products by title, description, or category."""
        pattern = f"%{query.strip()}%"
        statement = (
            select(Product)
            .where(
                Product.is_active.is_(True),
                or_(
                    Product.title.ilike(pattern),
                    Product.description.ilike(pattern),
                    Product.category.ilike(pattern),
                ),
            )
            .order_by(Product.title.asc())
        )
        return list(self.session.execute(statement).scalars().all())
