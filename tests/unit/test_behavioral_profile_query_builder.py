"""Tests for deterministic BehavioralProfile retrieval-query construction."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.ai.retrieval.query_builder import (
    BehavioralProfileQueryBuilder,
    RetrievalQuery,
)
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _profile(
    interests: list[InterestScore],
    *,
    signal_strength: float = 1.0,
) -> BehavioralProfile:
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
        signal_strength=signal_strength,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=False,
            reason=RecommendationTriggerReason.INSUFFICIENT_SIGNAL,
        ),
    )


def _interest(name: str, score: float) -> InterestScore:
    return InterestScore(interest=name, score=score, raw_score=score * 10)


def test_query_preserves_ranked_interests_in_order() -> None:
    profile = _profile(
        [_interest("Agentic AI", 1.0), _interest("LangGraph", 0.8), _interest("Python", 0.6)]
    )

    result = BehavioralProfileQueryBuilder().build(profile)

    assert result == RetrievalQuery(
        text="Agentic AI, LangGraph, Python",
        interests_used=("Agentic AI", "LangGraph", "Python"),
        sufficient_signal=True,
    )


def test_query_uses_configured_top_n_ranked_interests() -> None:
    profile = _profile(
        [_interest("first", 1.0), _interest("second", 0.8), _interest("third", 0.6)]
    )

    result = BehavioralProfileQueryBuilder(max_interests=2).build(profile)

    assert result.interests_used == ("first", "second")
    assert result.text == "first, second"


def test_query_deduplicates_interest_text_without_changing_rank_order() -> None:
    profile = _profile(
        [
            _interest("  Agentic   AI  ", 1.0),
            _interest("agentic ai", 0.8),
            _interest("LangGraph", 0.6),
        ]
    )

    result = BehavioralProfileQueryBuilder().build(profile)

    assert result.interests_used == ("Agentic AI", "LangGraph")
    assert result.text == "Agentic AI, LangGraph"


def test_empty_ranked_interests_produce_an_explicit_insufficient_result() -> None:
    result = BehavioralProfileQueryBuilder().build(_profile([], signal_strength=0.0))

    assert result == RetrievalQuery(text="", interests_used=(), sufficient_signal=False)


def test_zero_signal_does_not_invent_a_query_even_when_interests_are_present() -> None:
    result = BehavioralProfileQueryBuilder().build(
        _profile([_interest("Agentic AI", 1.0)], signal_strength=0.0)
    )

    assert result == RetrievalQuery(text="", interests_used=(), sufficient_signal=False)


def test_positive_low_signal_with_ranked_interests_remains_usable() -> None:
    result = BehavioralProfileQueryBuilder().build(
        _profile([_interest("Agentic AI", 1.0)], signal_strength=0.2)
    )

    assert result.sufficient_signal is True
    assert result.text == "Agentic AI"


def test_same_profile_produces_the_same_query() -> None:
    profile = _profile([_interest("Agentic AI", 1.0), _interest("LangGraph", 0.8)])
    builder = BehavioralProfileQueryBuilder()

    assert builder.build(profile) == builder.build(profile)


def test_builder_rejects_non_positive_max_interests() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        BehavioralProfileQueryBuilder(max_interests=0)
