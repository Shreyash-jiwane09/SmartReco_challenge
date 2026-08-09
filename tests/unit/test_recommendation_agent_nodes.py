"""Behavioral tests for the minimal recommendation graph nodes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.agent.nodes import (
    RecommendationGroundingError,
    RecommendationWorkflowError,
    build_generate_recommendation_node,
    prepare_recommendation_context,
    validate_recommendation_grounding,
)
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


class _FakeRecommendationClient:
    def __init__(self, result: GeneratedRecommendation | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.prompts: list[object] = []

    def generate(self, prompt: object) -> GeneratedRecommendation:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _profile() -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=[InterestScore(interest="Agentic AI", score=1.0, raw_score=4.0)],
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


def _product() -> RetrievedProduct:
    return RetrievedProduct(
        product_id=uuid4(),
        title="Agentic AI Fundamentals",
        description="Learn practical agent workflows.",
        category="AI",
        price=Decimal("79.00"),
        distance=0.1,
    )


def _recommendation(product_id) -> GeneratedRecommendation:
    return GeneratedRecommendation(
        narrative="A tailored course for your agentic AI interests.",
        recommendations=[
            RecommendedProduct(product_id=product_id, reason="Matches your recent interest.")
        ],
    )


def _state(profile: BehavioralProfile, products: list[RetrievedProduct]) -> RecommendationAgentState:
    return {
        "profile": profile,
        "retrieved_products": products,
        "generated_recommendation": None,
        "failure": None,
    }


def test_prepare_context_accepts_real_profile_and_retrieved_products() -> None:
    assert prepare_recommendation_context(_state(_profile(), [_product()])) == {}


def test_prepare_context_rejects_empty_retrieval_before_mesh_can_be_called() -> None:
    client = _FakeRecommendationClient()

    with pytest.raises(RecommendationWorkflowError, match="at least one retrieved product"):
        prepare_recommendation_context(_state(_profile(), []))

    assert client.prompts == []


def test_generation_node_builds_prompt_and_returns_generated_recommendation() -> None:
    profile = _profile()
    product = _product()
    recommendation = _recommendation(product.product_id)
    client = _FakeRecommendationClient(result=recommendation)
    node = build_generate_recommendation_node(client)  # type: ignore[arg-type]

    update = node(_state(profile, [product]))

    assert client.prompts[0].system
    assert str(product.product_id) in client.prompts[0].user
    assert update == {"generated_recommendation": recommendation, "failure": None}


def test_generation_node_propagates_mesh_client_failure() -> None:
    node = build_generate_recommendation_node(
        _FakeRecommendationClient(error=RuntimeError("Mesh unavailable"))  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match="Mesh unavailable"):
        node(_state(_profile(), [_product()]))


def test_generation_node_does_not_mutate_frozen_upstream_inputs() -> None:
    profile = _profile()
    product = _product()
    profile_before = profile.model_copy(deep=True)
    product_before = product
    node = build_generate_recommendation_node(
        _FakeRecommendationClient(result=_recommendation(product.product_id))  # type: ignore[arg-type]
    )

    node(_state(profile, [product]))

    assert profile == profile_before
    assert product is product_before


def test_grounding_accepts_all_selected_products_from_candidates() -> None:
    first_product = _product()
    second_product = _product()
    state = _state(_profile(), [first_product, second_product])
    state["generated_recommendation"] = GeneratedRecommendation(
        narrative="Two relevant courses.",
        recommendations=[
            RecommendedProduct(product_id=first_product.product_id, reason="Matches agent interests."),
            RecommendedProduct(product_id=second_product.product_id, reason="Builds graph skills."),
        ],
    )

    assert validate_recommendation_grounding(state) == {}


def test_grounding_rejects_unknown_structurally_valid_product_id() -> None:
    product = _product()
    state = _state(_profile(), [product])
    state["generated_recommendation"] = _recommendation(uuid4())

    with pytest.raises(RecommendationGroundingError, match="catalog grounding failed"):
        validate_recommendation_grounding(state)


def test_grounding_rejects_mixed_valid_and_unknown_product_ids_completely() -> None:
    product = _product()
    state = _state(_profile(), [product])
    state["generated_recommendation"] = GeneratedRecommendation(
        narrative="Mixed selections.",
        recommendations=[
            RecommendedProduct(product_id=product.product_id, reason="A valid choice."),
            RecommendedProduct(product_id=uuid4(), reason="An invalid choice."),
        ],
    )

    with pytest.raises(RecommendationGroundingError, match="catalog grounding failed"):
        validate_recommendation_grounding(state)


def test_grounding_rejects_missing_generated_recommendation() -> None:
    with pytest.raises(RecommendationGroundingError, match="requires a generated recommendation"):
        validate_recommendation_grounding(_state(_profile(), [_product()]))


def test_grounding_does_not_mutate_recommendation_or_retrieved_products() -> None:
    product = _product()
    generated = _recommendation(product.product_id)
    state = _state(_profile(), [product])
    state["generated_recommendation"] = generated
    client = _FakeRecommendationClient()

    validate_recommendation_grounding(state)

    assert state["generated_recommendation"] is generated
    assert state["retrieved_products"] == [product]
    assert client.prompts == []
