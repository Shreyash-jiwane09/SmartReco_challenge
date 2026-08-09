"""Tests for deterministic recommendation refresh trigger decisions."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.behavior.triggers import evaluate_recommendation_trigger
from app.models.event import Event, EventType
from app.schemas.behavior import (
    BehavioralProfile,
    BehaviorEvidence,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)
from app.services.behavior import BehaviorProfileService


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _profile(
    *,
    total_events: int = 3,
    signal_strength: float = 1.0,
    searches: int = 0,
    time_spent_seconds: float = 0.0,
    interests: list[InterestScore] | None = None,
    evidence: list[BehaviorEvidence] | None = None,
) -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=interests or [],
        evidence=evidence or [],
        recent_activity=RecentActivitySummary(
            total_events=total_events,
            product_views=0,
            searches=searches,
            clicks=0,
            time_spent_seconds=time_spent_seconds,
            latest_event_at=REFERENCE_TIME,
            window_start=REFERENCE_TIME - timedelta(days=30),
        ),
        signal_strength=signal_strength,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=False,
            reason=RecommendationTriggerReason.INSUFFICIENT_SIGNAL,
        ),
    )


def _search_evidence() -> BehaviorEvidence:
    return BehaviorEvidence(
        interest="boots",
        event_type=EventType.SEARCH,
        source="search",
        contribution=4.0,
        occurred_at=REFERENCE_TIME,
    )


@pytest.mark.parametrize(
    ("profile", "reason"),
    [
        (_profile(total_events=0, signal_strength=0.0), RecommendationTriggerReason.INSUFFICIENT_SIGNAL),
        (_profile(total_events=2), RecommendationTriggerReason.INSUFFICIENT_SIGNAL),
        (_profile(signal_strength=0.8), RecommendationTriggerReason.INSUFFICIENT_SIGNAL),
    ],
)
def test_insufficient_history_or_signal_does_not_trigger(
    profile: BehavioralProfile, reason: RecommendationTriggerReason
) -> None:
    trigger = evaluate_recommendation_trigger(profile, reference_time=REFERENCE_TIME)

    assert trigger.recommendation_refresh is False
    assert trigger.reason is reason


def test_sufficient_search_intent_triggers_refresh_deterministically() -> None:
    profile = _profile(searches=1, evidence=[_search_evidence()])

    assert evaluate_recommendation_trigger(profile, reference_time=REFERENCE_TIME) == (
        evaluate_recommendation_trigger(profile, reference_time=REFERENCE_TIME)
    )
    assert evaluate_recommendation_trigger(
        profile, reference_time=REFERENCE_TIME
    ).reason is RecommendationTriggerReason.SEARCH_INTENT


def test_sufficient_high_engagement_triggers_refresh() -> None:
    trigger = evaluate_recommendation_trigger(
        _profile(time_spent_seconds=120), reference_time=REFERENCE_TIME
    )

    assert trigger.recommendation_refresh is True
    assert trigger.reason is RecommendationTriggerReason.HIGH_ENGAGEMENT


def test_sufficient_ranked_interest_triggers_refresh() -> None:
    trigger = evaluate_recommendation_trigger(
        _profile(interests=[InterestScore(interest="boots", score=1.0, raw_score=5.0)]),
        reference_time=REFERENCE_TIME,
    )

    assert trigger.recommendation_refresh is True
    assert trigger.reason is RecommendationTriggerReason.NEW_MEANINGFUL_INTEREST


@pytest.mark.parametrize("profile", [_profile(evidence=[_search_evidence()]), _profile(time_spent_seconds=120)])
def test_active_or_future_cooldown_overrides_other_triggers(profile: BehavioralProfile) -> None:
    trigger = evaluate_recommendation_trigger(
        profile,
        reference_time=REFERENCE_TIME,
        last_recommendation_at=REFERENCE_TIME - timedelta(minutes=1),
    )
    future_trigger = evaluate_recommendation_trigger(
        profile,
        reference_time=REFERENCE_TIME,
        last_recommendation_at=REFERENCE_TIME + timedelta(minutes=1),
    )

    assert trigger.reason is RecommendationTriggerReason.COOLDOWN_ACTIVE
    assert future_trigger.reason is RecommendationTriggerReason.COOLDOWN_ACTIVE


def test_expired_or_absent_cooldown_allows_triggering() -> None:
    profile = _profile(evidence=[_search_evidence()])

    assert evaluate_recommendation_trigger(
        profile,
        reference_time=REFERENCE_TIME,
        last_recommendation_at=REFERENCE_TIME - timedelta(minutes=30),
    ).reason is RecommendationTriggerReason.SEARCH_INTENT
    assert evaluate_recommendation_trigger(
        profile, reference_time=REFERENCE_TIME
    ).reason is RecommendationTriggerReason.SEARCH_INTENT


def test_naive_timestamps_are_rejected() -> None:
    profile = _profile(evidence=[_search_evidence()])

    with pytest.raises(ValueError, match="reference_time must be timezone-aware"):
        evaluate_recommendation_trigger(
            profile, reference_time=REFERENCE_TIME.replace(tzinfo=None)
        )
    with pytest.raises(ValueError, match="last_recommendation_at must be timezone-aware"):
        evaluate_recommendation_trigger(
            profile,
            reference_time=REFERENCE_TIME,
            last_recommendation_at=REFERENCE_TIME.replace(tzinfo=None),
        )


class _EventRepository:
    def __init__(self, events: list[Event]) -> None:
        self.events = events

    def list_by_user_time_range(self, user_id, start_time, end_time):
        return [event for event in self.events if start_time <= event.event_timestamp <= end_time]


class _ProductRepository:
    def get_by_id(self, product_id):
        return None


def test_profile_service_uses_the_real_trigger_evaluator() -> None:
    user_id = uuid4()
    events = [
        Event(
            id=uuid4(),
            user_id=user_id,
            session_id="session-1",
            event_type=EventType.SEARCH,
            event_timestamp=REFERENCE_TIME,
            event_metadata={"query": "boots"},
        )
        for _ in range(3)
    ]
    service = BehaviorProfileService(_EventRepository(events), _ProductRepository())

    profile = service.generate_profile(user_id, REFERENCE_TIME)

    assert profile.trigger.recommendation_refresh is True
    assert profile.trigger.reason is RecommendationTriggerReason.SEARCH_INTENT
