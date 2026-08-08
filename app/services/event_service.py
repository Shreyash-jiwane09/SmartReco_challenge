"""Behavioral event application service operations."""

from __future__ import annotations

from app.models.event import Event
from app.repositories.event import EventRepository
from app.schemas.event import EventBatchSchema


class EventService:
    """Coordinate validated behavioral event batch persistence."""

    def __init__(self, repository: EventRepository) -> None:
        self.repository = repository

    def create_many(self, batch: EventBatchSchema) -> list[Event]:
        """Persist a validated event batch in a single transaction."""
        events = [
            Event(
                user_id=batch.session.user_id,
                session_id=batch.session.session_id,
                event_type=event.event_type,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                page_url=event.page_url,
                event_timestamp=event.event_timestamp,
                event_metadata=event.metadata,
            )
            for event in batch.events
        ]
        persisted_events = self.repository.create_many(events)
        self.repository.session.commit()
        return persisted_events
