"""Opt-in real-infrastructure verification for semantic Product retrieval."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.ai.retrieval.chroma import ProductChromaStore
from app.ai.retrieval.embeddings import MeshEmbeddingService
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.ai.retrieval.retriever import SemanticProductRetrievalService
from app.core.config import settings
from app.repositories.product import ProductRepository
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)
from app.schemas.product import ProductCreate
from app.services.product import ProductService
from app.services.vector_service import ProductVectorService


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
MESH_KEY_REQUIRED = "MESH_API_KEY must be configured to run real semantic retrieval E2E"
REAL_E2E_ENABLED = os.getenv("RUN_REAL_MESH_E2E", "").lower() == "true"
REAL_E2E_REQUIRED = (
    "Set RUN_REAL_MESH_E2E=true after confirming Mesh account balance "
    "to run real semantic retrieval E2E"
)


def _profile() -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=[
            InterestScore(interest="Agentic AI", score=1.0, raw_score=9.0),
            InterestScore(interest="LangGraph", score=0.9, raw_score=8.1),
            InterestScore(
                interest="Advanced LangGraph Agents", score=0.75, raw_score=6.75
            ),
        ],
        evidence=[],
        recent_activity=RecentActivitySummary(
            total_events=5,
            product_views=2,
            searches=2,
            clicks=1,
            time_spent_seconds=180.0,
            latest_event_at=REFERENCE_TIME,
            window_start=REFERENCE_TIME,
        ),
        signal_strength=1.0,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=True,
            reason=RecommendationTriggerReason.SEARCH_INTENT,
        ),
    )


@pytest.mark.skipif(
    not settings.mesh_api_key or not REAL_E2E_ENABLED,
    reason=MESH_KEY_REQUIRED if not settings.mesh_api_key else REAL_E2E_REQUIRED,
)
def test_real_mesh_chroma_and_sql_semantic_retrieval(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Verify the complete catalog indexing and SQL-grounded retrieval path."""
    embedding_service = MeshEmbeddingService(
        api_key=settings.mesh_api_key,
        model=settings.mesh_embedding_model,
    )
    store = ProductChromaStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name=f"{settings.chroma_collection_name}_semantic_e2e",
    )
    vector_service = ProductVectorService(embedding_service, store)
    product_repository = ProductRepository(db_session)
    product_service = ProductService(product_repository, vector_service)

    catalog = [
        ProductCreate(
            title="Agentic AI Fundamentals",
            description=(
                "An introductory course on autonomous AI agents, reasoning workflows, "
                "tool use, planning, and reliable agentic systems."
            ),
            category="Agentic AI",
            price=Decimal("79.00"),
        ),
        ProductCreate(
            title="Advanced LangGraph Agents",
            description=(
                "Build advanced LangGraph agents with stateful workflows, multi-agent "
                "orchestration, graph-based control flow, and durable execution."
            ),
            category="Agentic AI",
            price=Decimal("129.00"),
        ),
        ProductCreate(
            title="Pandas for Data Analysis",
            description=(
                "Learn Pandas DataFrames, tabular data manipulation, data cleaning, "
                "aggregation, and practical exploratory data analysis."
            ),
            category="Data Science",
            price=Decimal("69.00"),
        ),
        ProductCreate(
            title="FastAPI Fundamentals",
            description=(
                "Develop REST APIs with FastAPI, backend routing, request validation, "
                "dependency injection, and Python web services."
            ),
            category="Backend Development",
            price=Decimal("59.00"),
        ),
    ]
    products = [product_service.create_product(payload) for payload in catalog]
    products_by_id = {product.id: product for product in products}

    retrieval_service = SemanticProductRetrievalService(
        query_builder=BehavioralProfileQueryBuilder(),
        embedding_service=embedding_service,
        store=store,
        product_repository=product_repository,
        top_k=4,
    )
    profile = _profile()
    retrieval_query = BehavioralProfileQueryBuilder().build(profile)
    retrieved = retrieval_service.retrieve(profile)

    assert retrieval_query.text == (
        "Agentic AI, LangGraph, Advanced LangGraph Agents"
    )
    assert len(retrieved) == 4
    assert {item.product_id for item in retrieved} == set(products_by_id)
    assert all(products_by_id[item.product_id].is_active for item in retrieved)
    assert all(product_repository.get_by_id(item.product_id) is not None for item in retrieved)

    positions = {item.product_id: index for index, item in enumerate(retrieved)}
    agentic_ids: set[UUID] = {products[0].id, products[1].id}
    unrelated_ids: set[UUID] = {products[2].id, products[3].id}
    assert max(positions[product_id] for product_id in agentic_ids) < min(
        positions[product_id] for product_id in unrelated_ids
    )

    for item in retrieved:
        product = products_by_id[item.product_id]
        assert item.title == product.title
        assert item.description == product.description
        assert item.category == product.category
        assert item.price == product.price
