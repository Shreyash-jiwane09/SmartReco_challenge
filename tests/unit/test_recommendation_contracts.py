"""Tests for recommendation generation contracts and graph state."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.ai.agent.state import RecommendationAgentState
from app.ai.retrieval.retriever import RetrievedProduct
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)
from app.schemas.recommendation import GeneratedRecommendation, RecommendedProduct


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


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
            recommendation_refresh=True,
            reason=RecommendationTriggerReason.NEW_MEANINGFUL_INTEREST,
        ),
    )


def _retrieved_product() -> RetrievedProduct:
    return RetrievedProduct(
        product_id=uuid4(),
        title="Agentic AI Fundamentals",
        description="Learn practical agent workflows.",
        category="AI",
        price=Decimal("79.00"),
        distance=0.1,
    )


def test_recommended_product_accepts_a_uuid_and_reason() -> None:
    product_id = uuid4()

    recommendation = RecommendedProduct(
        product_id=product_id,
        reason="Matches your recent interest in agentic AI.",
    )

    assert recommendation.product_id == product_id


def test_generated_recommendation_accepts_multiple_distinct_products() -> None:
    first_product_id = uuid4()
    second_product_id = uuid4()

    generated = GeneratedRecommendation(
        narrative="These courses align with your recent learning activity.",
        recommendations=[
            RecommendedProduct(product_id=first_product_id, reason="Covers agent workflows."),
            RecommendedProduct(product_id=second_product_id, reason="Builds on graph concepts."),
        ],
    )

    assert [item.product_id for item in generated.recommendations] == [
        first_product_id,
        second_product_id,
    ]


@pytest.mark.parametrize("narrative", ["", "   "])
def test_generated_recommendation_rejects_empty_narrative(narrative: str) -> None:
    with pytest.raises(ValidationError):
        GeneratedRecommendation(
            narrative=narrative,
            recommendations=[RecommendedProduct(product_id=uuid4(), reason="Relevant choice.")],
        )


@pytest.mark.parametrize("reason", ["", "   "])
def test_recommended_product_rejects_empty_reason(reason: str) -> None:
    with pytest.raises(ValidationError):
        RecommendedProduct(product_id=uuid4(), reason=reason)


def test_generated_recommendation_rejects_an_empty_collection() -> None:
    with pytest.raises(ValidationError):
        GeneratedRecommendation(narrative="A tailored selection.", recommendations=[])


def test_generated_recommendation_rejects_duplicate_product_ids() -> None:
    product_id = uuid4()

    with pytest.raises(ValidationError, match="duplicate product IDs"):
        GeneratedRecommendation(
            narrative="A tailored selection.",
            recommendations=[
                RecommendedProduct(product_id=product_id, reason="First reason."),
                RecommendedProduct(product_id=product_id, reason="Second reason."),
            ],
        )


def test_recommended_product_rejects_an_invalid_uuid() -> None:
    with pytest.raises(ValidationError):
        RecommendedProduct(product_id="not-a-uuid", reason="Relevant choice.")


def test_agent_state_carries_real_upstream_profile_and_retrieved_products() -> None:
    profile = _profile()
    retrieved_product = _retrieved_product()
    state: RecommendationAgentState = {
        "profile": profile,
        "retrieved_products": [retrieved_product],
        "generated_recommendation": None,
        "failure": None,
    }

    assert state["profile"] is profile
    assert state["retrieved_products"] == [retrieved_product]
