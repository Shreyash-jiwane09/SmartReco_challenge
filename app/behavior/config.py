"""Centralized defaults for future behavior intelligence processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from app.models.event import EventType


def _default_event_weights() -> Mapping[EventType, float]:
    """Return default weights for supported event types."""
    return {
        EventType.PRODUCT_VIEW: 1.0,
        EventType.CLICK: 2.0,
        EventType.TIME_SPENT: 3.0,
        EventType.SEARCH: 4.0,
    }


@dataclass(frozen=True)
class BehaviorScoringConfig:
    """Immutable configuration for the deterministic behavior pipeline."""

    event_weights: Mapping[EventType, float] = field(default_factory=_default_event_weights)
    decay_half_life_hours: int = 72
    profile_window_days: int = 30
    max_interests: int = 10
    minimum_interest_score: float = 0.05
    minimum_trigger_events: int = 3
    trigger_score_threshold: float = 5.0
    cooldown_minutes: int = 30
    search_interest_multiplier: float = 1.0
    product_category_multiplier: float = 1.0
    product_title_multiplier: float = 0.5
    high_engagement_seconds: int = 120

    def __post_init__(self) -> None:
        """Prevent mutation of weights, including on custom config instances."""
        object.__setattr__(self, "event_weights", MappingProxyType(dict(self.event_weights)))


behavior_scoring_config = BehaviorScoringConfig()
