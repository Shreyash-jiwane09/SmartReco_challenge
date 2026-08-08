"""Tests for behavior intelligence configuration and output contracts."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.behavior.config import behavior_scoring_config
from app.models.event import EventType
from app.schemas.behavior import (
    BehavioralProfile,
    BehaviorEvidence,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _profile_payload() -> dict:
    timestamp = _timestamp()
    return {
        "user_id": uuid4(),
        "interests": [InterestScore(interest="running", score=0.8, raw_score=6.0)],
        "evidence": [
            BehaviorEvidence(
                interest="running",
                event_type=EventType.SEARCH,
                source="search query",
                contribution=4.0,
                occurred_at=timestamp,
            )
        ],
        "recent_activity": RecentActivitySummary(
            total_events=3,
            product_views=1,
            searches=1,
            clicks=1,
            time_spent_seconds=12.5,
            latest_event_at=timestamp,
            window_start=timestamp,
        ),
        "signal_strength": 0.8,
        "generated_at": timestamp,
        "trigger": RecommendationTrigger(
            recommendation_refresh=True,
            reason=RecommendationTriggerReason.SEARCH_INTENT,
        ),
    }


def test_event_weights_cover_existing_event_types_in_descending_priority() -> None:
    weights = behavior_scoring_config.event_weights

    assert set(weights) == set(EventType)
    assert (
        weights[EventType.SEARCH]
        > weights[EventType.TIME_SPENT]
        > weights[EventType.CLICK]
        > weights[EventType.PRODUCT_VIEW]
    )


def test_behavioral_profile_accepts_realistic_valid_data() -> None:
    profile = BehavioralProfile(**_profile_payload())

    assert profile.signal_strength == 0.8
    assert profile.trigger.reason is RecommendationTriggerReason.SEARCH_INTENT


@pytest.mark.parametrize("field,value", [("signal_strength", 1.1), ("signal_strength", -0.1)])
def test_behavioral_profile_rejects_out_of_range_signal_strength(
    field: str, value: float
) -> None:
    payload = _profile_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        BehavioralProfile(**payload)


@pytest.mark.parametrize("score", [1.1, -0.1])
def test_interest_score_rejects_out_of_range_normalized_score(score: float) -> None:
    with pytest.raises(ValidationError):
        InterestScore(interest="running", score=score, raw_score=1.0)


@pytest.mark.parametrize("field", ["total_events", "product_views", "searches", "clicks"])
def test_recent_activity_rejects_negative_counts(field: str) -> None:
    payload = {
        "total_events": 1,
        "product_views": 0,
        "searches": 0,
        "clicks": 0,
        "time_spent_seconds": 0.0,
        "window_start": _timestamp(),
    }
    payload[field] = -1

    with pytest.raises(ValidationError):
        RecentActivitySummary(**payload)
