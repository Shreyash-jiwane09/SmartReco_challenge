"""PostgreSQL integration tests for the event repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.models.user import User
from app.repositories.event import EventRepository


def _create_user(session: Session, email: str) -> User:
    user = User(
        email=email,
        hashed_password="hashed-password",
        full_name="Test User",
    )
    session.add(user)
    session.flush()
    return user


def _event(
    user: User,
    timestamp: datetime,
    *,
    session_id: str = "session-1",
    event_type: EventType = EventType.PRODUCT_VIEW,
) -> Event:
    return Event(
        user_id=user.id,
        session_id=session_id,
        event_type=event_type,
        resource_type="product",
        resource_id="product-1",
        event_timestamp=timestamp,
        event_metadata={},
    )


def test_create_persists_event_flushes_without_committing(db_session: Session) -> None:
    user = _create_user(db_session, "create@example.com")
    repository = EventRepository(db_session)
    event = _event(user, datetime.now(timezone.utc))

    persisted = repository.create(event)

    assert persisted is event
    assert persisted.id is not None
    assert db_session.in_transaction()
    assert db_session.execute(select(Event).where(Event.id == event.id)).scalar_one() is event


def test_create_many_persists_input_events_without_committing(db_session: Session) -> None:
    user = _create_user(db_session, "many@example.com")
    repository = EventRepository(db_session)
    start = datetime.now(timezone.utc)
    events = [_event(user, start + timedelta(seconds=index)) for index in range(3)]

    persisted = repository.create_many(events)

    assert persisted == events
    assert [event.id for event in persisted] == [event.id for event in events]
    assert all(event.id is not None for event in persisted)
    assert db_session.in_transaction()
    assert len(db_session.execute(select(Event)).scalars().all()) == 3


def test_get_by_id_returns_existing_event_or_none(db_session: Session) -> None:
    user = _create_user(db_session, "lookup@example.com")
    repository = EventRepository(db_session)
    event = repository.create(_event(user, datetime.now(timezone.utc)))

    assert repository.get_by_id(event.id) is event
    assert repository.get_by_id(uuid4()) is None


def test_list_by_user_isolated_ordered_paginated_and_filterable(
    db_session: Session,
) -> None:
    first_user = _create_user(db_session, "first@example.com")
    second_user = _create_user(db_session, "second@example.com")
    repository = EventRepository(db_session)
    start = datetime.now(timezone.utc)
    first = _event(first_user, start + timedelta(seconds=3), event_type=EventType.SEARCH)
    second = _event(first_user, start + timedelta(seconds=1), event_type=EventType.CLICK)
    third = _event(first_user, start + timedelta(seconds=2), event_type=EventType.CLICK)
    repository.create_many([first, second, third, _event(second_user, start)])

    assert repository.list_by_user(first_user.id) == [second, third, first]
    assert repository.list_by_user(first_user.id, offset=1, limit=1) == [third]
    assert repository.list_by_user(first_user.id, event_type=EventType.CLICK) == [second, third]


def test_list_by_session_isolated_ordered_and_paginated(db_session: Session) -> None:
    user = _create_user(db_session, "session@example.com")
    repository = EventRepository(db_session)
    start = datetime.now(timezone.utc)
    first = _event(user, start + timedelta(seconds=2), session_id="shared")
    second = _event(user, start + timedelta(seconds=1), session_id="shared")
    repository.create_many([first, second, _event(user, start, session_id="other")])

    assert repository.list_by_session("shared") == [second, first]
    assert repository.list_by_session("shared", offset=1, limit=1) == [first]


def test_list_by_user_time_range_is_inclusive_ordered_and_filterable(
    db_session: Session,
) -> None:
    user = _create_user(db_session, "range@example.com")
    repository = EventRepository(db_session)
    start = datetime.now(timezone.utc).replace(microsecond=0)
    before = _event(user, start - timedelta(seconds=1))
    at_start = _event(user, start, event_type=EventType.CLICK)
    middle = _event(user, start + timedelta(seconds=1), event_type=EventType.SEARCH)
    at_end = _event(user, start + timedelta(seconds=2), event_type=EventType.CLICK)
    after = _event(user, start + timedelta(seconds=3))
    repository.create_many([before, at_end, middle, after, at_start])

    assert repository.list_by_user_time_range(
        user.id,
        start,
        start + timedelta(seconds=2),
    ) == [at_start, middle, at_end]
    assert repository.list_by_user_time_range(
        user.id,
        start,
        start + timedelta(seconds=2),
        event_type=EventType.CLICK,
        offset=1,
        limit=1,
    ) == [at_end]
