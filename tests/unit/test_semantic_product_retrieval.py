"""Unit tests for SQL-grounded semantic Product retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.ai.retrieval.chroma import ProductVectorCandidate
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.ai.retrieval.retriever import (
    ACTIVE_PRODUCT_FILTER,
    SemanticProductRetrievalService,
)
from app.models.product import Product
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _profile(*, interests: list[InterestScore] | None = None) -> BehavioralProfile:
    interests = interests if interests is not None else [
        InterestScore(interest="Agentic AI", score=1.0, raw_score=5.0)
    ]
    return BehavioralProfile(
        user_id=uuid4(),
        interests=interests,
        evidence=[],
        recent_activity=RecentActivitySummary(
            total_events=len(interests),
            product_views=0,
            searches=0,
            clicks=0,
            time_spent_seconds=0.0,
            latest_event_at=REFERENCE_TIME if interests else None,
            window_start=REFERENCE_TIME,
        ),
        signal_strength=1.0 if interests else 0.0,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=False,
            reason=RecommendationTriggerReason.INSUFFICIENT_SIGNAL,
        ),
    )


class _EmbeddingService:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.1, 0.2]


class _Store:
    def __init__(self, candidates: list[ProductVectorCandidate]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[list[float], int, dict[str, bool] | None]] = []

    def query_products(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, bool] | None,
    ) -> list[ProductVectorCandidate]:
        self.calls.append((query_embedding, top_k, where))
        return self.candidates


class _Repository:
    def __init__(self, products: list[Product]) -> None:
        self.products = {product.id: product for product in products}
        self.ids: list[UUID] = []

    def get_by_id(self, product_id: UUID) -> Product | None:
        self.ids.append(product_id)
        return self.products.get(product_id)


def _product(*, title: str, is_active: bool = True) -> Product:
    return Product(
        id=uuid4(),
        title=title,
        description=f"SQL description for {title}",
        category="SQL category",
        price=Decimal("19.99"),
        is_active=is_active,
    )


def _service(
    candidates: list[ProductVectorCandidate], products: list[Product], *, top_k: int = 5
) -> tuple[SemanticProductRetrievalService, _EmbeddingService, _Store, _Repository]:
    embedding_service = _EmbeddingService()
    store = _Store(candidates)
    repository = _Repository(products)
    return (
        SemanticProductRetrievalService(
            query_builder=BehavioralProfileQueryBuilder(),
            embedding_service=embedding_service,  # type: ignore[arg-type]
            store=store,  # type: ignore[arg-type]
            product_repository=repository,  # type: ignore[arg-type]
            top_k=top_k,
        ),
        embedding_service,
        store,
        repository,
    )


def test_insufficient_profile_returns_empty_without_embedding_or_chroma_query() -> None:
    service, embedding_service, store, _ = _service([], [])

    assert service.retrieve(_profile(interests=[])) == []
    assert embedding_service.texts == []
    assert store.calls == []


def test_retrieval_embeds_once_and_passes_top_k_and_active_filter() -> None:
    product = _product(title="Authoritative Product")
    service, embedding_service, store, _ = _service(
        [ProductVectorCandidate(product_id=str(product.id), distance=0.12)], [product], top_k=3
    )

    result = service.retrieve(_profile())

    assert embedding_service.texts == ["Agentic AI"]
    assert store.calls == [([0.1, 0.2], 3, ACTIVE_PRODUCT_FILTER)]
    assert result[0].title == "Authoritative Product"
    assert result[0].description == "SQL description for Authoritative Product"
    assert result[0].category == "SQL category"
    assert result[0].price == Decimal("19.99")


def test_retrieval_preserves_chroma_order_and_skips_stale_invalid_inactive_and_duplicates() -> None:
    first = _product(title="First")
    inactive = _product(title="Inactive", is_active=False)
    second = _product(title="Second")
    service, _, _, repository = _service(
        [
            ProductVectorCandidate(product_id=str(first.id), distance=0.1),
            ProductVectorCandidate(product_id=str(uuid4()), distance=0.2),
            ProductVectorCandidate(product_id="not-a-uuid", distance=0.3),
            ProductVectorCandidate(product_id=str(inactive.id), distance=0.4),
            ProductVectorCandidate(product_id=str(first.id), distance=0.5),
            ProductVectorCandidate(product_id=str(second.id), distance=0.6),
        ],
        [first, inactive, second],
    )

    result = service.retrieve(_profile())

    assert [item.product_id for item in result] == [first.id, second.id]
    assert [item.distance for item in result] == [0.1, 0.6]
    assert repository.ids.count(first.id) == 1


def test_empty_chroma_candidates_return_empty_result() -> None:
    service, embedding_service, store, _ = _service([], [])

    assert service.retrieve(_profile(), top_k=2) == []
    assert embedding_service.texts == ["Agentic AI"]
    assert store.calls[0][1] == 2


def test_retrieval_rejects_non_positive_top_k() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        _service([], [], top_k=0)
