"""Repository operations for behavioral events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    """Provide append-oriented persistence and retrieval for behavioral events."""

    def __init__(self, session: Session) -> None:
        super().__init__(Event, session)

    def create_many(self, events: list[Event]) -> list[Event]:
        """Add events to the current transaction without committing."""
        self.session.add_all(events)
        self.session.flush()
        return events

    def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int | None = None,
        event_type: EventType | None = None,
    ) -> list[Event]:
        """Return a user's events in deterministic chronological order."""
        statement = select(Event).where(Event.user_id == user_id)
        if event_type is not None:
            statement = statement.where(Event.event_type == event_type)
        return self._list_chronologically(statement, offset=offset, limit=limit)

    def list_by_session(
        self,
        session_id: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Event]:
        """Return a session's events in deterministic chronological order."""
        statement = select(Event).where(Event.session_id == session_id)
        return self._list_chronologically(statement, offset=offset, limit=limit)

    def list_by_user_time_range(
        self,
        user_id: uuid.UUID,
        start_time: datetime,
        end_time: datetime,
        *,
        event_type: EventType | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Event]:
        """Return a user's events within an inclusive time range."""
        statement = select(Event).where(
            Event.user_id == user_id,
            Event.event_timestamp >= start_time,
            Event.event_timestamp <= end_time,
        )
        if event_type is not None:
            statement = statement.where(Event.event_type == event_type)
        return self._list_chronologically(statement, offset=offset, limit=limit)

    def _list_chronologically(
        self,
        statement: Select[tuple[Event]],
        *,
        offset: int,
        limit: int | None,
    ) -> list[Event]:
        """Apply the shared chronological ordering and pagination convention."""
        statement = statement.order_by(
            Event.event_timestamp.asc(),
            Event.created_at.asc(),
            Event.id.asc(),
        ).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.execute(statement).scalars().all())
