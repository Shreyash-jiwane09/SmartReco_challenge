"""Product service operations."""

from __future__ import annotations

import uuid

from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.vector_service import ProductVectorService


class ProductServiceError(Exception):
    """Base exception for product service failures."""


class ProductNotFoundError(ProductServiceError):
    """Raised when a requested product does not exist."""


class ProductVectorSyncError(ProductServiceError):
    """Raised when Product SQL and vector synchronization cannot complete."""


class ProductService:
    """Coordinate product persistence operations."""

    def __init__(
        self,
        repository: ProductRepository,
        vector_service: ProductVectorService,
    ) -> None:
        self.repository = repository
        self.vector_service = vector_service

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
        self._upsert_product_vector(product, operation="create")
        self.repository.session.commit()
        self.repository.session.refresh(product)
        return product

    def update_product(self, product_id: uuid.UUID, data: ProductUpdate) -> Product:
        """Update and persist a product."""
        product = self.get_product(product_id)
        values = data.model_dump(exclude_unset=True)
        self.repository.update(product, values)
        self._upsert_product_vector(product, operation="update")
        self.repository.session.commit()
        self.repository.session.refresh(product)
        return product

    def delete_product(self, product_id: uuid.UUID) -> Product:
        """Delete a product and commit the transaction."""
        product = self.get_product(product_id)
        try:
            self.vector_service.delete_product(product.id)
        except Exception as exc:
            self.repository.session.rollback()
            raise ProductVectorSyncError(
                f"Unable to synchronize Product {product_id} deletion with vector storage"
            ) from exc
        self.repository.delete(product)
        self.repository.session.commit()
        return product

    def _upsert_product_vector(self, product: Product, *, operation: str) -> None:
        """Index Product changes before committing their SQL transaction."""
        try:
            product.chroma_document_id = self.vector_service.upsert_product(product)
            product.embedding_version = self.vector_service.embedding_model
        except Exception as exc:
            self.repository.session.rollback()
            raise ProductVectorSyncError(
                f"Unable to synchronize Product {product.id} {operation} with vector storage"
            ) from exc
