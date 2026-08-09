"""Real PostgreSQL and Chroma verification of ProductService dual-write."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.retrieval.chroma import ProductChromaStore
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product import ProductService
from app.services.vector_service import ProductVectorService


class _FakeEmbeddingService:
    model = "test/embedding-model"

    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 0.25, -0.25]


def test_product_service_keeps_sql_and_real_chroma_in_sync(
    db_session: Session,
    tmp_path: Path,
) -> None:
    store = ProductChromaStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="product_service_dual_write",
    )
    vector_service = ProductVectorService(_FakeEmbeddingService(), store)  # type: ignore[arg-type]
    service = ProductService(ProductRepository(db_session), vector_service)

    product = service.create_product(
        ProductCreate(
            title="Agentic AI Basics",
            description="Learn dependable agent patterns.",
            category="AI",
            price=Decimal("49.00"),
        )
    )
    product_id = str(product.id)
    created = store.collection.get(ids=[product_id], include=["documents", "metadatas"])
    assert created["ids"] == [product_id]
    assert product.chroma_document_id == product_id
    assert product.embedding_version == "test/embedding-model"

    updated = service.update_product(
        product.id,
        ProductUpdate(
            title="Advanced Agentic AI",
            description="Build and evaluate dependable agent workflows.",
            category="Agentic AI",
        ),
    )
    refreshed = store.collection.get(ids=[product_id], include=["documents", "metadatas"])
    assert refreshed["ids"] == [product_id]
    assert refreshed["documents"] == [
        "Title: Advanced Agentic AI\n"
        "Category: Agentic AI\n"
        "Description: Build and evaluate dependable agent workflows."
    ]
    assert store.collection.count() == 1

    service.update_product(product.id, ProductUpdate(is_active=False))
    inactive = store.collection.get(ids=[product_id], include=["metadatas"])
    assert inactive["metadatas"] == [
        {
            "product_id": product_id,
            "category": "Agentic AI",
            "price": 49.0,
            "is_active": False,
        }
    ]

    service.delete_product(updated.id)
    assert store.collection.get(ids=[product_id])["ids"] == []
