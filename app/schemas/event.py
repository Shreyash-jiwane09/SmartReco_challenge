"""Pydantic schemas for behavioral event ingestion."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.models.event import EventType


class SessionContextSchema(BaseModel):
    """Session-level identity shared by a batch of events."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    session_id: str = Field(min_length=1, max_length=255)


class ClientContextSchema(BaseModel):
    """Optional extensibility container for client context."""

    model_config = ConfigDict(from_attributes=True)


class EventSchema(BaseModel):
    """Validated structure for one behavioral event."""

    model_config = ConfigDict(from_attributes=True)

    event_type: EventType
    resource_type: str | None = Field(default=None, min_length=1, max_length=100)
    resource_id: str | None = Field(default=None, min_length=1, max_length=255)
    page_url: str | None = Field(default=None, max_length=2048)
    event_timestamp: datetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event_payload(self) -> EventSchema:
        """Validate event-specific fields required by the event contract."""
        if self.event_type in {EventType.PRODUCT_VIEW, EventType.CLICK}:
            if self.resource_type is None or self.resource_id is None:
                raise ValueError(
                    "resource_type and resource_id are required for this event type"
                )

        if self.event_type is EventType.SEARCH:
            query = self.metadata.get("query")
            if not isinstance(query, str) or not query.strip():
                raise ValueError("metadata.query is required for SEARCH events")

        if self.event_type is EventType.TIME_SPENT:
            duration = self.metadata.get("duration")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool):
                raise ValueError(
                    "metadata.duration is required for TIME_SPENT events"
                )
            if duration < 0:
                raise ValueError("metadata.duration must not be negative")

        if (
            self.event_timestamp.tzinfo is None
            or self.event_timestamp.utcoffset() is None
        ):
            raise ValueError("event_timestamp must be timezone-aware")

        return self


class EventBatchSchema(BaseModel):
    """Event envelope containing shared context and ordered events."""

    model_config = ConfigDict(from_attributes=True)

    session: SessionContextSchema
    client: ClientContextSchema
    events: list[EventSchema] = Field(min_length=1)


class EventResponseSchema(BaseModel):
    """Acknowledgement returned after event ingestion."""

    model_config = ConfigDict(from_attributes=True)

    accepted: bool
    received: int = Field(ge=0)
