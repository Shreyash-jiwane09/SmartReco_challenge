"""Real Chroma integration coverage for SQL-grounded semantic retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.retrieval.chroma import ProductChromaStore
from app.ai.retrieval.product_document import build_product_document, build_product_metadata
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.ai.retrieval.retriever import SemanticProductRetrievalService
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


class _FakeEmbeddingService:
    def embed(self, _text: str) -> list[float]:
        return [0.0, 0.0]


def _profile() -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=[InterestScore(interest="Agentic AI", score=1.0, raw_score=5.0)],
        evidence=[],
        recent_activity=RecentActivitySummary(
            total_events=1,
            product_views=1,
            searches=0,
            clicks=0,
            time_spent_seconds=0.0,
            latest_event_at=REFERENCE_TIME,
            window_start=REFERENCE_TIME,
        ),
        signal_strength=1.0,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=False,
            reason=RecommendationTriggerReason.INSUFFICIENT_SIGNAL,
        ),
    )


def _product(title: str, *, is_active: bool = True) -> Product:
    return Product(
        title=title,
        description=f"SQL description for {title}",
        category="Courses",
        price=Decimal("49.00"),
        is_active=is_active,
    )


def test_real_chroma_retrieval_applies_filter_and_resolves_sql_products(
    db_session: Session,
    tmp_path: Path,
) -> None:
    repository = ProductRepository(db_session)
    agentic = repository.create(_product("Agentic AI Fundamentals"))
    langgraph = repository.create(_product("Advanced LangGraph Agents"))
    pandas = repository.create(_product("Pandas for Data Analysis"))
    fastapi = repository.create(_product("FastAPI Fundamentals", is_active=False))
    db_session.commit()

    store = ProductChromaStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="semantic_product_retrieval",
    )
    vectors = {
        agentic.id: [0.0, 0.0],
        langgraph.id: [0.1, 0.0],
        pandas.id: [1.0, 0.0],
        fastapi.id: [0.01, 0.0],
    }
    for product in [agentic, langgraph, pandas, fastapi]:
        store.upsert_product(
            product_id=str(product.id),
            document=build_product_document(product),
            metadata=build_product_metadata(product),
            embedding=vectors[product.id],
        )

    service = SemanticProductRetrievalService(
        query_builder=BehavioralProfileQueryBuilder(),
        embedding_service=_FakeEmbeddingService(),  # type: ignore[arg-type]
        store=store,
        product_repository=repository,
        top_k=2,
    )
    first_result = service.retrieve(_profile())
    assert [item.product_id for item in first_result] == [agentic.id, langgraph.id]
    assert all(item.product_id != fastapi.id for item in first_result)

    agentic.title = "Authoritative Agentic AI Fundamentals"
    db_session.commit()
    stale_id = str(uuid4())
    store.upsert_product(
        product_id=stale_id,
        document="stale",
        metadata={"product_id": stale_id, "category": "Courses", "price": 1.0, "is_active": True},
        embedding=[0.01, 0.0],
    )

    second_result = service.retrieve(_profile(), top_k=3)
    assert [item.product_id for item in second_result] == [agentic.id, langgraph.id]
    assert second_result[0].title == "Authoritative Agentic AI Fundamentals"
    assert second_result[0].description == agentic.description
    assert second_result[0].category == agentic.category
    assert second_result[0].price == agentic.price
