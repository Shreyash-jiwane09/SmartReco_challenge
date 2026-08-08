"""Deterministic weighting of persisted behavioral events."""

from __future__ import annotations

from app.behavior.config import behavior_scoring_config
from app.models.event import Event
from app.schemas.behavior import WeightedBehaviorSignal


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
