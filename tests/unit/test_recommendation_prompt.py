"""Tests for deterministic recommendation prompt construction."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from uuid import uuid4

from app.ai.agent.prompts import build_recommendation_prompt
from app.ai.retrieval.retriever import RetrievedProduct
from app.models.event import EventType
from app.schemas.behavior import (
    BehavioralProfile,
    BehaviorEvidence,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _profile() -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=[
            InterestScore(interest="Agentic AI", score=1.0, raw_score=4.0),
            InterestScore(interest="LangGraph", score=0.8, raw_score=3.2),
        ],
        evidence=[
            BehaviorEvidence(
                interest="Agentic AI",
                event_type=EventType.SEARCH,
                source="search",
                contribution=4.0,
                occurred_at=REFERENCE_TIME,
            )
        ],
        recent_activity=RecentActivitySummary(
            total_events=2,
            product_views=1,
            searches=1,
            clicks=0,
            time_spent_seconds=45.0,
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


def _product() -> RetrievedProduct:
    return RetrievedProduct(
        product_id=uuid4(),
        title="Advanced LangGraph Agents",
        description="Build dependable stateful agent workflows.",
        category="Agentic AI",
        price=Decimal("129.00"),
        distance=0.12345,
    )


def test_prompt_includes_compact_profile_and_catalog_context() -> None:
    product = _product()

    prompt = build_recommendation_prompt(_profile(), [product])
    payload = json.loads(prompt.user)

    assert payload["behavioral_profile"]["interests"] == [
        {"interest": "Agentic AI", "score": 1.0},
        {"interest": "LangGraph", "score": 0.8},
    ]
    assert payload["catalog_candidates"] == [
        {
            "product_id": str(product.product_id),
            "title": "Advanced LangGraph Agents",
            "description": "Build dependable stateful agent workflows.",
            "category": "Agentic AI",
            "price": "129.00",
        }
    ]
    assert "0.12345" not in prompt.user


def test_prompt_makes_catalog_only_and_personalized_output_rules_explicit() -> None:
    prompt = build_recommendation_prompt(_profile(), [_product()])

    assert "only products you may select" in prompt.system
    assert "must exactly\nmatch a supplied candidate ID" in prompt.system
    assert "Do not invent products, IDs, titles, categories, prices" in prompt.system
    assert "personalized and persuasive" in prompt.system
    assert "user-specific reason" in prompt.system
