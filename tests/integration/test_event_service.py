"""PostgreSQL integration tests for the event service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.models.user import User
from app.repositories.event import EventRepository
from app.schemas.event import EventBatchSchema
from app.services.event_service import EventService


def _create_user(session: Session) -> User:
    user = User(
        email=f"event-service-{uuid4()}@example.com",
        hashed_password="hashed-password",
        full_name="Event Service Test User",
    )
    session.add(user)
    session.flush()
    return user


def _event_payload(event_type: EventType, timestamp: datetime) -> dict:
    payload: dict = {
        "event_type": event_type,
        "event_timestamp": timestamp,
        "metadata": {},
    }
    if event_type in {EventType.PRODUCT_VIEW, EventType.CLICK}:
        payload.update(resource_type="product", resource_id="product-1")
    elif event_type is EventType.SEARCH:
        payload["metadata"] = {"query": "running shoes"}
    else:
        payload["metadata"] = {"duration": 4.5}
    return payload


def _batch(user: User, events: list[dict]) -> EventBatchSchema:
    return EventBatchSchema(
        session={"user_id": user.id, "session_id": "session-1"},
        client={},
        events=events,
    )


def test_empty_batch_is_rejected_by_schema_before_service_construction() -> None:
    with pytest.raises(ValidationError):
        EventBatchSchema(
            session={"user_id": uuid4(), "session_id": "session-1"},
            client={},
            events=[],
        )


def test_create_many_persists_single_event_with_shared_context_and_metadata(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    timestamp = datetime.now(timezone.utc)
    payload = _event_payload(EventType.SEARCH, timestamp)
    payload["metadata"] = {"query": "waterproof boots", "source": "header"}

    persisted = EventService(EventRepository(db_session)).create_many(
        _batch(user, [payload])
    )

    assert len(persisted) == 1
    event = persisted[0]
    assert isinstance(event, Event)
    assert event.user_id == user.id
    assert event.session_id == "session-1"
    assert event.event_type is EventType.SEARCH
    assert event.resource_type is None
    assert event.event_metadata == payload["metadata"]
    assert db_session.execute(select(Event).where(Event.id == event.id)).scalar_one() is event


def test_create_many_persists_all_event_types_in_input_order(db_session: Session) -> None:
    user = _create_user(db_session)
    start = datetime.now(timezone.utc)
    event_types = list(EventType)
    events = [
        _event_payload(event_type, start + timedelta(seconds=index))
        for index, event_type in enumerate(event_types)
    ]

    persisted = EventService(EventRepository(db_session)).create_many(_batch(user, events))

    assert [event.event_type for event in persisted] == event_types
    assert [event.event_timestamp for event in persisted] == [
        event["event_timestamp"] for event in events
    ]
    assert all(event.user_id == user.id for event in persisted)
    assert all(event.session_id == "session-1" for event in persisted)


def test_create_many_uses_one_repository_call_and_one_commit() -> None:
    session = Mock()
    repository = Mock(spec=EventRepository)
    repository.session = session
    repository.create_many.side_effect = lambda events: events
    timestamp = datetime.now(timezone.utc)
    batch = EventBatchSchema(
        session={"user_id": uuid4(), "session_id": "session-1"},
        client={},
        events=[
            _event_payload(EventType.PRODUCT_VIEW, timestamp),
            _event_payload(EventType.CLICK, timestamp + timedelta(seconds=1)),
        ],
    )

    persisted = EventService(repository).create_many(batch)

    repository.create_many.assert_called_once()
    session.commit.assert_called_once_with()
    assert persisted == repository.create_many.call_args.args[0]
