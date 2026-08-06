"""Product service operations."""

from __future__ import annotations

import uuid

from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate


class ProductServiceError(Exception):
    """Base exception for product service failures."""


class ProductNotFoundError(ProductServiceError):
    """Raised when a requested product does not exist."""


class ProductService:
    """Coordinate product persistence operations."""

    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def get_product(self, product_id: uuid.UUID) -> Product:
        """Return a product by identifier or raise a domain exception."""
        product = self.repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(f"Product {product_id} was not found")
        return product

    def list_products(
        self,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Product]:
        """Return products from the repository."""
        return self.repository.list(offset=offset, limit=limit)

    def create_product(self, data: ProductCreate) -> Product:
        """Create and persist a product."""
        product = Product(
            title=data.title,
            description=data.description,
            category=data.category,
            price=data.price,
            is_active=data.is_active,
        )
        self.repository.create(product)
        self.repository.session.commit()
        self.repository.session.refresh(product)
        return product

    def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        """Update and persist a product."""
        product = self.get_product(product_id)
        values = data.model_dump(exclude_unset=True)
        self.repository.update(product, values)
        self.repository.session.commit()
        self.repository.session.refresh(product)
        return product

    def delete_product(self, product_id: uuid.UUID) -> Product:
        """Delete a product and commit the transaction."""
        product = self.get_product(product_id)
        self.repository.delete(product)
        self.repository.session.commit()
        return product
