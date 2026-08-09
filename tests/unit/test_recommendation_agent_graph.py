"""Behavioral tests for the compiled recommendation LangGraph workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.agent.graph import build_recommendation_graph
from app.ai.agent.nodes import RecommendationWorkflowError
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
        self.calls = 0

    def generate(self, _prompt: object) -> GeneratedRecommendation:
        self.calls += 1
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


def _state(products: list[RetrievedProduct]) -> RecommendationAgentState:
    return {
        "profile": _profile(),
        "retrieved_products": products,
        "generated_recommendation": None,
        "failure": None,
    }


def _recommendation(product_id) -> GeneratedRecommendation:
    return GeneratedRecommendation(
        narrative="A tailored course for your agentic AI interests.",
        recommendations=[
            RecommendedProduct(product_id=product_id, reason="Matches your recent interest.")
        ],
    )


def test_graph_compiles_and_generates_one_recommendation() -> None:
    product = _product()
    recommendation = _recommendation(product.product_id)
    client = _FakeRecommendationClient(result=recommendation)

    graph = build_recommendation_graph(client)  # type: ignore[arg-type]
    result = graph.invoke(_state([product]))

    assert result["generated_recommendation"] == recommendation
    assert result["failure"] is None
    assert client.calls == 1


def test_graph_rejects_empty_retrieval_before_client_invocation() -> None:
    client = _FakeRecommendationClient()
    graph = build_recommendation_graph(client)  # type: ignore[arg-type]

    with pytest.raises(RecommendationWorkflowError, match="at least one retrieved product"):
        graph.invoke(_state([]))

    assert client.calls == 0


def test_graph_propagates_client_exception() -> None:
    client = _FakeRecommendationClient(error=RuntimeError("Mesh unavailable"))
    graph = build_recommendation_graph(client)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="Mesh unavailable"):
        graph.invoke(_state([_product()]))

    assert client.calls == 1
