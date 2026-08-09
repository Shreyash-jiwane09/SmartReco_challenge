"""Opt-in real-infrastructure verification for recommendation generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.ai.agent.graph import build_recommendation_graph
from app.ai.mesh.client import MeshRecommendationClient
from app.ai.retrieval.chroma import ProductChromaStore
from app.ai.retrieval.embeddings import MeshEmbeddingService
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.ai.retrieval.retriever import SemanticProductRetrievalService
from app.core.config import settings
from app.models.event import Event, EventType
from app.models.user import User
from app.repositories.event import EventRepository
from app.repositories.product import ProductRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.user import UserRepository
from app.schemas.product import ProductCreate
from app.services.behavior import BehaviorProfileService
from app.services.product import ProductService
from app.services.recommendation_service import (
    RecommendationGenerationStatus,
    RecommendationService,
)
from app.services.vector_service import ProductVectorService


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
MESH_KEY_REQUIRED = "MESH_API_KEY must be configured to run real recommendation E2E"
REAL_E2E_ENABLED = os.getenv("RUN_REAL_MESH_E2E", "").lower() == "true"
REAL_E2E_REQUIRED = (
    "Set RUN_REAL_MESH_E2E=true after confirming Mesh account balance "
    "to run real recommendation E2E"
)


@pytest.mark.skipif(
    not settings.mesh_api_key or not REAL_E2E_ENABLED,
    reason=MESH_KEY_REQUIRED if not settings.mesh_api_key else REAL_E2E_REQUIRED,
)
def test_real_mesh_recommendation_pipeline_persists_catalog_grounded_result(
    db_session: Session,
    tmp_path: Path,
) -> None:
    """Prove real behavior, retrieval, Mesh chat, grounding, and persistence work together."""
    embedding_service = MeshEmbeddingService(
        api_key=settings.mesh_api_key,
        model=settings.mesh_embedding_model,
    )
    store = ProductChromaStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name=f"{settings.chroma_collection_name}_recommendation_e2e",
    )
    vector_service = ProductVectorService(embedding_service, store)
    product_repository = ProductRepository(db_session)
    product_service = ProductService(product_repository, vector_service)
    event_repository = EventRepository(db_session)
    recommendation_repository = RecommendationRepository(db_session)

    user = UserRepository(db_session).create(
        User(
            email="recommendation-e2e@example.com",
            hashed_password="hashed-password",
            full_name="Recommendation E2E User",
        )
    )
    catalog = [
        ProductCreate(
            title="Agentic AI Fundamentals",
            description=(
                "Learn autonomous AI agents, tool use, planning, reasoning workflows, "
                "and dependable agentic systems."
            ),
            category="Agentic AI",
            price=Decimal("79.00"),
        ),
        ProductCreate(
            title="Advanced LangGraph Agents",
            description=(
                "Build stateful LangGraph agents with graph-based control flow, "
                "durable execution, and advanced orchestration."
            ),
            category="Agentic AI",
            price=Decimal("129.00"),
        ),
        ProductCreate(
            title="Practical AI Agent Evaluation",
            description=(
                "Evaluate AI agent reliability, tool calling, task completion, "
                "and production-ready agent workflows."
            ),
            category="Agentic AI",
            price=Decimal("99.00"),
        ),
        ProductCreate(
            title="Pandas for Data Analysis",
            description=(
                "Learn DataFrames, tabular data cleaning, aggregation, "
                "and exploratory data analysis with Pandas."
            ),
            category="Data Science",
            price=Decimal("69.00"),
        ),
    ]
    products = [product_service.create_product(payload) for payload in catalog]
    catalog_product_ids = {product.id for product in products}

    event_repository.create_many(
        [
            Event(
                user_id=user.id,
                session_id="recommendation-e2e-session",
                event_type=EventType.PRODUCT_VIEW,
                resource_type="product",
                resource_id=str(products[0].id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=20),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="recommendation-e2e-session",
                event_type=EventType.PRODUCT_VIEW,
                resource_type="product",
                resource_id=str(products[0].id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=18),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="recommendation-e2e-session",
                event_type=EventType.SEARCH,
                event_timestamp=REFERENCE_TIME - timedelta(minutes=15),
                event_metadata={"query": "LangGraph agentic AI agents"},
            ),
            Event(
                user_id=user.id,
                session_id="recommendation-e2e-session",
                event_type=EventType.CLICK,
                resource_type="product",
                resource_id=str(products[1].id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=10),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="recommendation-e2e-session",
                event_type=EventType.TIME_SPENT,
                resource_type="product",
                resource_id=str(products[1].id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=5),
                event_metadata={"duration": 180.0},
            ),
        ]
    )
    db_session.commit()

    behavior_profile_service = BehaviorProfileService(event_repository, product_repository)
    retrieval_service = SemanticProductRetrievalService(
        query_builder=BehavioralProfileQueryBuilder(),
        embedding_service=embedding_service,
        store=store,
        product_repository=product_repository,
        top_k=len(products),
    )
    recommendation_client = MeshRecommendationClient(
        api_key=settings.mesh_api_key,
        model=settings.mesh_chat_model,
    )
    service = RecommendationService(
        behavior_profile_service,
        retrieval_service,
        recommendation_repository,
        build_recommendation_graph(recommendation_client),
    )

    result = service.generate_for_user(user.id, reference_time=REFERENCE_TIME)

    assert result.status is RecommendationGenerationStatus.GENERATED
    assert result.profile.user_id == user.id
    assert result.profile.trigger.recommendation_refresh is True
    assert result.profile.interests

    recommendation = result.recommendation
    assert recommendation is not None
    assert recommendation.id is not None
    assert recommendation.user_id == user.id
    assert recommendation.narrative.strip()
    assert recommendation.created_at is not None
    assert recommendation.products

    selected_product_ids = {item.product_id for item in recommendation.products}
    assert selected_product_ids <= catalog_product_ids
    assert all(item.reason.strip() for item in recommendation.products)
    assert [item.position for item in recommendation.products] == list(
        range(len(recommendation.products))
    )

    latest = recommendation_repository.get_latest_for_user(user.id)
    latest_created_at = recommendation_repository.get_latest_created_at_for_user(user.id)
    assert latest is not None
    assert latest.id == recommendation.id
    assert latest_created_at is not None
    assert latest_created_at == recommendation.created_at
