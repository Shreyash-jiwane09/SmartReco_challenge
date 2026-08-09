"""Tests for deterministic behavioral signal recency decay."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.behavior.config import behavior_scoring_config
from app.behavior.scoring import apply_recency_decay
from app.models.event import EventType
from app.schemas.behavior import WeightedBehaviorSignal


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _signal(occurred_at: datetime = REFERENCE_TIME, value: float = 4.0) -> WeightedBehaviorSignal:
    """Create a fixed weighted signal for decay calculations."""
    return WeightedBehaviorSignal(
        event_id=uuid4(),
        user_id=uuid4(),
        event_type=EventType.SEARCH,
        base_weight=4.0,
        signal_value=value,
        source="search",
        occurred_at=occurred_at,
        resource_id="product-42",
    )


def test_fresh_signal_has_a_decay_factor_of_one() -> None:
    decayed = apply_recency_decay(_signal(), REFERENCE_TIME)

    assert decayed.decay_factor == pytest.approx(1.0)


def test_signal_one_half_life_old_has_half_influence() -> None:
    signal = _signal(
        REFERENCE_TIME - timedelta(hours=behavior_scoring_config.decay_half_life_hours)
    )

    decayed = apply_recency_decay(signal, REFERENCE_TIME)

    assert decayed.decay_factor == pytest.approx(0.5)


def test_signal_two_half_lives_old_has_quarter_influence() -> None:
    signal = _signal(
        REFERENCE_TIME
        - timedelta(hours=2 * behavior_scoring_config.decay_half_life_hours)
    )

    decayed = apply_recency_decay(signal, REFERENCE_TIME)

    assert decayed.decay_factor == pytest.approx(0.25)


def test_older_equivalent_signal_has_lower_decayed_value() -> None:
    newer = apply_recency_decay(_signal(REFERENCE_TIME - timedelta(hours=1)), REFERENCE_TIME)
    older = apply_recency_decay(_signal(REFERENCE_TIME - timedelta(hours=24)), REFERENCE_TIME)

    assert older.decayed_value < newer.decayed_value


def test_decayed_value_equals_signal_value_times_decay_factor() -> None:
    decayed = apply_recency_decay(_signal(REFERENCE_TIME - timedelta(hours=18)), REFERENCE_TIME)

    assert decayed.decayed_value == pytest.approx(
        decayed.signal_value * decayed.decay_factor
    )


def test_decayed_signal_preserves_weighted_signal_context() -> None:
    signal = _signal(REFERENCE_TIME - timedelta(hours=3))
    decayed = apply_recency_decay(signal, REFERENCE_TIME)

    assert decayed.event_id == signal.event_id
    assert decayed.user_id == signal.user_id
    assert decayed.event_type is signal.event_type
    assert decayed.base_weight == signal.base_weight
    assert decayed.signal_value == signal.signal_value
    assert decayed.source == signal.source
    assert decayed.occurred_at == signal.occurred_at
    assert decayed.resource_id == signal.resource_id


def test_future_signal_is_clamped_to_zero_age() -> None:
    decayed = apply_recency_decay(_signal(REFERENCE_TIME + timedelta(minutes=5)), REFERENCE_TIME)

    assert decayed.decay_factor == pytest.approx(1.0)
    assert decayed.decayed_value == pytest.approx(decayed.signal_value)


def test_naive_reference_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="reference_time must be timezone-aware"):
        apply_recency_decay(_signal(), REFERENCE_TIME.replace(tzinfo=None))
