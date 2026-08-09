"""Deterministic recommendation refresh trigger evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.behavior.config import behavior_scoring_config
from app.models.event import EventType
from app.schemas.behavior import (
    BehavioralProfile,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


def evaluate_recommendation_trigger(
    profile: BehavioralProfile,
    *,
    reference_time: datetime,
    last_recommendation_at: datetime | None = None,
) -> RecommendationTrigger:
    """Decide whether accumulated behavior warrants a recommendation refresh.

    ``signal_strength`` reaches 1.0 when Task 5's total decayed signal reaches
    the configured raw ``trigger_score_threshold``; this is the sufficient
    signal threshold used here.
    """
    _require_timezone(reference_time, "reference_time")
    if last_recommendation_at is not None:
        _require_timezone(last_recommendation_at, "last_recommendation_at")
        if reference_time - last_recommendation_at < timedelta(
            minutes=behavior_scoring_config.cooldown_minutes
        ):
            return _trigger(False, RecommendationTriggerReason.COOLDOWN_ACTIVE)

    if (
        profile.recent_activity.total_events
        < behavior_scoring_config.minimum_trigger_events
        or profile.signal_strength < 1.0
    ):
        return _trigger(False, RecommendationTriggerReason.INSUFFICIENT_SIGNAL)

    if any(evidence.event_type is EventType.SEARCH for evidence in profile.evidence):
        return _trigger(True, RecommendationTriggerReason.SEARCH_INTENT)

    if (
        profile.recent_activity.time_spent_seconds
        >= behavior_scoring_config.high_engagement_seconds
    ):
        return _trigger(True, RecommendationTriggerReason.HIGH_ENGAGEMENT)

    if profile.interests:
        return _trigger(True, RecommendationTriggerReason.NEW_MEANINGFUL_INTEREST)

    return _trigger(False, RecommendationTriggerReason.INSUFFICIENT_SIGNAL)


def _require_timezone(value: datetime, field_name: str) -> None:
    """Validate an explicit timezone using the behavior contract convention."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _trigger(
    recommendation_refresh: bool, reason: RecommendationTriggerReason
) -> RecommendationTrigger:
    """Build a trigger decision consistently across priority branches."""
    return RecommendationTrigger(
        recommendation_refresh=recommendation_refresh,
        reason=reason,
    )
