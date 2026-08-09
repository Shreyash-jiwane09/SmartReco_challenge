"""Unit tests for ProductService SQL and vector synchronization."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product import (
    ProductNotFoundError,
    ProductService,
    ProductVectorSyncError,
)


class _Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.refreshed: list[Product] = []

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, product: Product) -> None:
        self.refreshed.append(product)


class _ProductRepository:
    def __init__(self, products: list[Product] | None = None, events: list[str] | None = None) -> None:
        self.session = _Session()
        self.products = {product.id: product for product in products or []}
        self.events = events if events is not None else []
        self.deleted: list[Product] = []

    def get_by_id(self, product_id: UUID) -> Product | None:
        return self.products.get(product_id)

    def list(self, *, offset: int = 0, limit: int | None = None) -> list[Product]:
        products = list(self.products.values())[offset:]
        return products if limit is None else products[:limit]

    def create(self, product: Product) -> Product:
        if product.id is None:
            product.id = uuid4()
        self.products[product.id] = product
        self.events.append("sql-create")
        return product

    def update(self, product: Product, values: dict[str, object]) -> Product:
        for field, value in values.items():
            setattr(product, field, value)
        self.events.append("sql-update")
        return product

    def delete(self, product: Product) -> Product:
        self.deleted.append(product)
        self.events.append("sql-delete")
        return product


class _VectorService:
    embedding_model = "openai/text-embedding-3-small"

    def __init__(self, events: list[str] | None = None, *, fail: bool = False) -> None:
        self.events = events if events is not None else []
        self.fail = fail
        self.upserted: list[Product] = []
        self.deleted: list[UUID] = []

    def upsert_product(self, product: Product) -> str:
        self.events.append("vector-upsert")
        if self.fail:
            raise RuntimeError("vector unavailable")
        self.upserted.append(product)
        return str(product.id)

    def delete_product(self, product_id: UUID) -> None:
        self.events.append("vector-delete")
        if self.fail:
            raise RuntimeError("vector unavailable")
        self.deleted.append(product_id)


def _product() -> Product:
    return Product(
        id=uuid4(),
        title="Original title",
        description="Original description",
        category="AI",
        price=Decimal("10.00"),
        is_active=True,
    )


def _create_payload() -> ProductCreate:
    return ProductCreate(
        title="Created title",
        description="Created description",
        category="Data",
        price=Decimal("20.00"),
    )


def test_create_indexes_the_flushed_product_and_records_vector_bookkeeping() -> None:
    repository = _ProductRepository()
    vector_service = _VectorService()

    product = ProductService(repository, vector_service).create_product(_create_payload())

    assert vector_service.upserted == [product]
    assert product.chroma_document_id == str(product.id)
    assert product.embedding_version == vector_service.embedding_model
    assert repository.session.commits == 1
    assert repository.session.rollbacks == 0


def test_create_rolls_back_when_vector_indexing_fails() -> None:
    repository = _ProductRepository()

    with pytest.raises(ProductVectorSyncError, match="create"):
        ProductService(repository, _VectorService(fail=True)).create_product(_create_payload())

    assert repository.session.commits == 0
    assert repository.session.rollbacks == 1


def test_update_upserts_all_changed_product_fields() -> None:
    product = _product()
    repository = _ProductRepository([product])
    vector_service = _VectorService()

    updated = ProductService(repository, vector_service).update_product(
        product.id,
        ProductUpdate(
            title="Updated title",
            description="Updated description",
            category="Agentic AI",
            price=Decimal("25.50"),
            is_active=False,
        ),
    )

    assert vector_service.upserted == [updated]
    assert updated.title == "Updated title"
    assert updated.description == "Updated description"
    assert updated.category == "Agentic AI"
    assert updated.price == Decimal("25.50")
    assert updated.is_active is False
    assert updated.chroma_document_id == str(product.id)
    assert repository.session.commits == 1


def test_update_rolls_back_when_vector_indexing_fails() -> None:
    product = _product()
    repository = _ProductRepository([product])

    with pytest.raises(ProductVectorSyncError, match="update"):
        ProductService(repository, _VectorService(fail=True)).update_product(
            product.id,
            ProductUpdate(is_active=False),
        )

    assert repository.session.commits == 0
    assert repository.session.rollbacks == 1


def test_delete_removes_vector_before_sql_product() -> None:
    product = _product()
    events: list[str] = []
    repository = _ProductRepository([product], events)
    vector_service = _VectorService(events)

    deleted = ProductService(repository, vector_service).delete_product(product.id)

    assert deleted is product
    assert vector_service.deleted == [product.id]
    assert repository.deleted == [product]
    assert events == ["vector-delete", "sql-delete"]
    assert repository.session.commits == 1


def test_delete_rolls_back_and_skips_sql_deletion_when_vector_delete_fails() -> None:
    product = _product()
    repository = _ProductRepository([product])

    with pytest.raises(ProductVectorSyncError, match="deletion"):
        ProductService(repository, _VectorService(fail=True)).delete_product(product.id)

    assert repository.deleted == []
    assert repository.session.commits == 0
    assert repository.session.rollbacks == 1


def test_delete_preserves_product_not_found_behavior() -> None:
    with pytest.raises(ProductNotFoundError):
        ProductService(_ProductRepository(), _VectorService()).delete_product(uuid4())
