"""Persistence-independent schemas for behavior intelligence output."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.event import EventType


class InterestScore(BaseModel):
    """An interest inferred from recent behavioral activity."""

    model_config = ConfigDict(from_attributes=True)

    interest: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    raw_score: float = Field(ge=0.0)


class BehaviorEvidence(BaseModel):
    """A single event contribution supporting an inferred interest."""

    model_config = ConfigDict(from_attributes=True)

    interest: str = Field(min_length=1)
    event_type: EventType
    source: str = Field(min_length=1)
    contribution: float = Field(ge=0.0)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at_timezone(cls, value: datetime) -> datetime:
        """Require an explicit timezone, matching the event contract."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class WeightedBehaviorSignal(BaseModel):
    """A deterministic weighted signal derived from one behavioral event."""

    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    user_id: UUID
    event_type: EventType
    base_weight: float = Field(ge=0.0)
    signal_value: float = Field(ge=0.0)
    source: str = Field(min_length=1)
    occurred_at: datetime
    resource_id: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at_timezone(cls, value: datetime) -> datetime:
        """Require an explicit timezone, matching the event contract."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class RecentActivitySummary(BaseModel):
    """Aggregate behavioral activity for the configured profile window."""

    model_config = ConfigDict(from_attributes=True)

    total_events: int = Field(ge=0)
    product_views: int = Field(ge=0)
    searches: int = Field(ge=0)
    clicks: int = Field(ge=0)
    time_spent_seconds: float = Field(ge=0.0)
    latest_event_at: datetime | None = None
    window_start: datetime

    @field_validator("latest_event_at", "window_start")
    @classmethod
    def validate_summary_timestamp_timezone(cls, value: datetime | None) -> datetime | None:
        """Require explicit timezones for supplied activity timestamps."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("activity timestamps must be timezone-aware")
        return value


class RecommendationTriggerReason(str, Enum):
    """Machine-readable reason for a recommendation refresh decision."""

    INSUFFICIENT_SIGNAL = "insufficient_signal"
    NEW_MEANINGFUL_INTEREST = "new_meaningful_interest"
    SEARCH_INTENT = "search_intent"
    HIGH_ENGAGEMENT = "high_engagement"
    PROFILE_CHANGED = "profile_changed"
    COOLDOWN_ACTIVE = "cooldown_active"


class RecommendationTrigger(BaseModel):
    """Declared refresh decision without trigger evaluation logic."""

    model_config = ConfigDict(from_attributes=True)

    recommendation_refresh: bool
    reason: RecommendationTriggerReason


class BehavioralProfile(BaseModel):
    """Computed behavioral profile returned by future intelligence processing."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    interests: list[InterestScore]
    evidence: list[BehaviorEvidence]
    recent_activity: RecentActivitySummary
    signal_strength: float = Field(ge=0.0, le=1.0)
    generated_at: datetime
    trigger: RecommendationTrigger

    @field_validator("generated_at")
    @classmethod
    def validate_generated_at_timezone(cls, value: datetime) -> datetime:
        """Require an explicit timezone for profile generation time."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value
