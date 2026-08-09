"""Focused tests for deterministic Product vector preparation and Mesh embeddings."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.retrieval.embeddings import EmbeddingError, MeshEmbeddingService
from app.ai.retrieval.product_document import (
    build_product_document,
    build_product_metadata,
)
from app.models.product import Product


def _product() -> Product:
    return Product(
        id=uuid4(),
        title="Agentic AI Fundamentals",
        category="AI Courses",
        description="Build reliable agent workflows.",
        price=Decimal("99.50"),
        is_active=False,
        chroma_document_id="not-in-document",
        embedding_version="v1",
    )


def test_product_document_is_deterministic_and_semantic_only() -> None:
    product = _product()

    assert build_product_document(product) == (
        "Title: Agentic AI Fundamentals\n"
        "Category: AI Courses\n"
        "Description: Build reliable agent workflows."
    )
    document = build_product_document(product)
    assert str(product.id) not in document
    assert "99.50" not in document
    assert "not-in-document" not in document
    assert "v1" not in document
    assert "False" not in document


def test_product_metadata_uses_chroma_supported_primitives() -> None:
    product = _product()

    assert build_product_metadata(product) == {
        "product_id": str(product.id),
        "category": "AI Courses",
        "price": 99.5,
        "is_active": False,
    }


class _EmbeddingClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[object] = []
        self.embeddings = self

    def create(self, params: object) -> object:
        self.calls.append(params)
        return self.response


def test_mesh_embedding_service_returns_numeric_vector() -> None:
    client = _EmbeddingClient(
        SimpleNamespace(data=[SimpleNamespace(embedding=[1, 2.5, -3])])
    )
    service = MeshEmbeddingService(
        api_key="test-key",
        model="openai/text-embedding-3-small",
        client=client,
    )

    assert service.embed("catalog text") == [1.0, 2.5, -3.0]
    assert client.calls[0].model == "openai/text-embedding-3-small"
    assert client.calls[0].input == "catalog text"


@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(data=[]),
        SimpleNamespace(data=[SimpleNamespace(embedding=[])]),
        SimpleNamespace(data=[SimpleNamespace(embedding=[1, "invalid"])]),
    ],
)
def test_mesh_embedding_service_rejects_malformed_responses(response: object) -> None:
    service = MeshEmbeddingService(
        api_key="test-key",
        model="openai/text-embedding-3-small",
        client=_EmbeddingClient(response),
    )

    with pytest.raises(EmbeddingError):
        service.embed("catalog text")
