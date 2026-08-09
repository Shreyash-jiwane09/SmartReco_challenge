"""Real Chroma verification for Product vector indexing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.ai.retrieval.chroma import ProductChromaStore
from app.models.product import Product
from app.services.vector_service import ProductVectorService


class _FakeEmbeddingService:
    def embed(self, text: str) -> list[float]:
        return [float(len(text)), 0.5, -0.5]


def _product(*, title: str, category: str, price: str) -> Product:
    return Product(
        id=uuid4(),
        title=title,
        category=category,
        description=f"Description for {title}.",
        price=Decimal(price),
        is_active=True,
    )


def _service(path: Path) -> tuple[ProductVectorService, ProductChromaStore]:
    store = ProductChromaStore(
        persist_directory=str(path),
        collection_name="test_products",
    )
    return ProductVectorService(_FakeEmbeddingService(), store), store  # type: ignore[arg-type]


def test_real_chroma_upsert_replaces_and_deletes_only_target_product(tmp_path: Path) -> None:
    service, store = _service(tmp_path / "chroma")
    first = _product(title="First Course", category="AI", price="10.00")
    second = _product(title="Second Course", category="Data", price="20.00")

    assert service.upsert_product(first) == str(first.id)
    service.upsert_product(second)

    stored_first = store.collection.get(
        ids=[str(first.id)], include=["documents", "metadatas"]
    )
    assert stored_first["ids"] == [str(first.id)]
    assert stored_first["documents"] == [
        "Title: First Course\nCategory: AI\nDescription: Description for First Course."
    ]
    assert stored_first["metadatas"] == [
        {
            "product_id": str(first.id),
            "category": "AI",
            "price": 10.0,
            "is_active": True,
        }
    ]

    first.title = "Revised First Course"
    first.category = "Agentic AI"
    first.description = "Updated semantic content."
    first.price = Decimal("15.25")
    first.is_active = False
    service.upsert_product(first)

    replaced_first = store.collection.get(
        ids=[str(first.id)], include=["documents", "metadatas"]
    )
    assert replaced_first["documents"] == [
        "Title: Revised First Course\n"
        "Category: Agentic AI\n"
        "Description: Updated semantic content."
    ]
    assert replaced_first["metadatas"] == [
        {
            "product_id": str(first.id),
            "category": "Agentic AI",
            "price": 15.25,
            "is_active": False,
        }
    ]

    service.delete_product(first.id)
    assert store.collection.get(ids=[str(first.id)])["ids"] == []
    assert store.collection.get(ids=[str(second.id)])["ids"] == [str(second.id)]
