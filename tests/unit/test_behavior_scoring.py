"""Tests for deterministic behavioral event weighting."""

from datetime import datetime, timezone
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.behavior.config import behavior_scoring_config
from app.behavior.scoring import weight_event
from app.models.event import Event, EventType


def _event(event_type: EventType, resource_id: str | None = "product-1") -> Event:
    """Create an in-memory event suitable for deterministic scoring tests."""
    return Event(
        id=uuid4(),
        user_id=uuid4(),
        session_id="session-1",
        event_type=event_type,
        resource_id=resource_id,
        event_timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("event_type", list(EventType))
def test_event_receives_its_configured_weight(event_type: EventType) -> None:
    signal = weight_event(_event(event_type))

    assert signal.base_weight == behavior_scoring_config.event_weights[event_type]
    assert signal.signal_value == signal.base_weight
    assert signal.source == event_type.value.lower()


def test_event_weight_priority_is_search_then_time_spent_then_click_then_view() -> None:
    weights = [weight_event(_event(event_type)).signal_value for event_type in EventType]

    assert weights == [1.0, 4.0, 2.0, 3.0]
    assert weights[1] > weights[3] > weights[2] > weights[0]


def test_weighted_signal_preserves_event_identity_and_context() -> None:
    event = _event(EventType.CLICK, resource_id="product-42")
    signal = weight_event(event)

    assert signal.event_id == event.id
    assert signal.user_id == event.user_id
    assert signal.event_type is event.event_type
    assert signal.occurred_at == event.event_timestamp
    assert signal.resource_id == event.resource_id


def test_unsupported_event_type_fails_explicitly() -> None:
    event = _event(EventType.CLICK)
    event.event_type = cast(EventType, "UNSUPPORTED")

    with pytest.raises(ValueError, match="Unsupported event type"):
        weight_event(event)
