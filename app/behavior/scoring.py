"""Deterministic weighting of persisted behavioral events."""

from __future__ import annotations

from datetime import datetime

from app.behavior.config import behavior_scoring_config
from app.models.event import Event
from app.schemas.behavior import DecayedBehaviorSignal, WeightedBehaviorSignal


def weight_event(event: Event) -> WeightedBehaviorSignal:
    """Convert an event to its configured base-weight behavioral signal."""
    try:
        base_weight = behavior_scoring_config.event_weights[event.event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported event type: {event.event_type!r}") from exc

    return WeightedBehaviorSignal(
        event_id=event.id,
        user_id=event.user_id,
        event_type=event.event_type,
        base_weight=base_weight,
        signal_value=base_weight,
        source=event.event_type.value.lower(),
        occurred_at=event.event_timestamp,
        resource_id=event.resource_id,
    )


def apply_recency_decay(
    signal: WeightedBehaviorSignal, reference_time: datetime
) -> DecayedBehaviorSignal:
    """Apply configured half-life decay to a weighted behavior signal."""
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("reference_time must be timezone-aware")

    age_hours = max(
        0.0,
        (reference_time - signal.occurred_at).total_seconds() / 3600,
    )
    decay_factor = 0.5 ** (
        age_hours / behavior_scoring_config.decay_half_life_hours
    )

    return DecayedBehaviorSignal(
        **signal.model_dump(),
        decay_factor=decay_factor,
        decayed_value=signal.signal_value * decay_factor,
    )
