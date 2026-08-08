"""Tests for behavioral event schemas."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.event import (
    ClientContextSchema,
    EventBatchSchema,
    EventResponseSchema,
    EventSchema,
    EventType,
    SessionContextSchema,
)


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def _event_payload(event_type: EventType) -> dict:
    payload = {
        "event_type": event_type,
        "event_timestamp": _timestamp(),
        "metadata": {},
    }
    if event_type in {EventType.PRODUCT_VIEW, EventType.CLICK}:
        payload.update(resource_type="product", resource_id="product-1")
    elif event_type is EventType.SEARCH:
        payload["metadata"] = {"query": "running shoes"}
    elif event_type is EventType.TIME_SPENT:
        payload["metadata"] = {"duration": 4.5}
    return payload


def test_event_type_accepts_all_approved_values() -> None:
    assert [event_type.value for event_type in EventType] == [
        "PRODUCT_VIEW",
        "SEARCH",
        "CLICK",
        "TIME_SPENT",
    ]


def test_event_type_rejects_unsupported_value() -> None:
    with pytest.raises(ValidationError):
        EventSchema(
            event_type="PURCHASE",
            event_timestamp=_timestamp(),
        )


def test_session_context_validates_uuid_and_session_id() -> None:
    context = SessionContextSchema(user_id=uuid4(), session_id="session-1")
    assert context.session_id == "session-1"

    with pytest.raises(ValidationError):
        SessionContextSchema(user_id="not-a-uuid", session_id="session-1")

    with pytest.raises(ValidationError):
        SessionContextSchema(user_id=uuid4(), session_id="")


def test_empty_client_context_is_valid() -> None:
    assert ClientContextSchema().model_dump() == {}


@pytest.mark.parametrize("event_type", list(EventType))
def test_valid_event_types_are_accepted(event_type: EventType) -> None:
    event = EventSchema(**_event_payload(event_type))
    assert event.event_type is event_type


def test_event_rejects_invalid_timestamp() -> None:
    payload = _event_payload(EventType.SEARCH)
    payload["event_timestamp"] = "not-a-timestamp"

    with pytest.raises(ValidationError):
        EventSchema(**payload)


def test_product_view_requires_resource_identification() -> None:
    payload = _event_payload(EventType.PRODUCT_VIEW)
    payload.pop("resource_type")
    payload.pop("resource_id")

    with pytest.raises(ValidationError):
        EventSchema(**payload)


def test_click_requires_resource_identification() -> None:
    payload = _event_payload(EventType.CLICK)
    payload.pop("resource_type")
    payload.pop("resource_id")

    with pytest.raises(ValidationError):
        EventSchema(**payload)


def test_search_requires_query_metadata() -> None:
    payload = _event_payload(EventType.SEARCH)
    payload["metadata"] = {}

    with pytest.raises(ValidationError):
        EventSchema(**payload)


def test_time_spent_rejects_negative_duration() -> None:
    payload = _event_payload(EventType.TIME_SPENT)
    payload["metadata"] = {"duration": -1}

    with pytest.raises(ValidationError):
        EventSchema(**payload)


def test_event_metadata_accepts_json_values() -> None:
    event = EventSchema(
        event_type=EventType.SEARCH,
        event_timestamp=_timestamp(),
        metadata={
            "query": "boots",
            "text": "value",
            "number": 3.5,
            "boolean": True,
            "null": None,
            "object": {"nested": "value"},
            "array": ["one", 2, False],
        },
    )

    assert event.metadata["object"] == {"nested": "value"}


def test_event_metadata_rejects_non_json_values() -> None:
    with pytest.raises(ValidationError):
        EventSchema(
            event_type=EventType.SEARCH,
            event_timestamp=_timestamp(),
            metadata={"query": "boots", "invalid": {1, 2}},
        )


def test_event_batch_validates_nested_events_and_preserves_order() -> None:
    events = [
        EventSchema(**_event_payload(EventType.PRODUCT_VIEW)),
        EventSchema(**_event_payload(EventType.SEARCH)),
        EventSchema(**_event_payload(EventType.TIME_SPENT)),
    ]
    batch = EventBatchSchema(
        session=SessionContextSchema(user_id=uuid4(), session_id="session-1"),
        client=ClientContextSchema(),
        events=events,
    )

    assert batch.events == events
    assert [event.event_type for event in batch.events] == [
        EventType.PRODUCT_VIEW,
        EventType.SEARCH,
        EventType.TIME_SPENT,
    ]


def test_event_batch_rejects_empty_events() -> None:
    with pytest.raises(ValidationError):
        EventBatchSchema(
            session=SessionContextSchema(user_id=uuid4(), session_id="session-1"),
            client=ClientContextSchema(),
            events=[],
        )


def test_event_batch_rejects_invalid_nested_event() -> None:
    payload = _event_payload(EventType.SEARCH)
    payload["metadata"] = {}

    with pytest.raises(ValidationError):
        EventBatchSchema(
            session=SessionContextSchema(user_id=uuid4(), session_id="session-1"),
            client=ClientContextSchema(),
            events=[payload],
        )


def test_event_response_accepts_non_negative_received_count() -> None:
    response = EventResponseSchema(accepted=True, received=8)
    assert response.received == 8

    with pytest.raises(ValidationError):
        EventResponseSchema(accepted=True, received=-1)
