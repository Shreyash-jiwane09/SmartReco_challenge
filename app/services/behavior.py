"""Orchestration for generating deterministic behavioral profiles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.behavior.config import behavior_scoring_config
from app.behavior.interests import extract_interests
from app.behavior.scoring import apply_recency_decay, weight_event
from app.behavior.triggers import evaluate_recommendation_trigger
from app.models.event import EventType
from app.repositories.event import EventRepository
from app.repositories.product import ProductRepository
from app.schemas.behavior import (
    BehavioralProfile,
    InterestExtractionInput,
    ProductInterestContext,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)


class BehaviorProfileService:
    """Generate a behavioral profile from a user's recent event history."""

    def __init__(
        self,
        event_repository: EventRepository,
        product_repository: ProductRepository,
    ) -> None:
        self.event_repository = event_repository
        self.product_repository = product_repository

    def generate_profile(
        self,
        user_id: UUID,
        reference_time: datetime | None = None,
        last_recommendation_at: datetime | None = None,
    ) -> BehavioralProfile:
        """Generate one internally consistent profile for a user."""
        if reference_time is None:
            reference_time = datetime.now(timezone.utc)
        elif reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")

        window_start = reference_time - timedelta(
            days=behavior_scoring_config.profile_window_days
        )
        events = self.event_repository.list_by_user_time_range(
            user_id,
            window_start,
            reference_time,
        )
        product_contexts: dict[str, ProductInterestContext | None] = {}
        extraction_inputs: list[InterestExtractionInput] = []
        total_decayed_signal = 0.0

        for event in events:
            decayed_signal = apply_recency_decay(weight_event(event), reference_time)
            total_decayed_signal += decayed_signal.decayed_value
            extraction_inputs.append(
                InterestExtractionInput(
                    signal=decayed_signal,
                    search_query=self._search_query(event.event_metadata)
                    if event.event_type is EventType.SEARCH
                    else None,
                    product=self._product_context(event.resource_id, product_contexts)
                    if event.event_type is not EventType.SEARCH
                    else None,
                )
            )

        extraction_result = extract_interests(extraction_inputs)
        profile = BehavioralProfile(
            user_id=user_id,
            interests=extraction_result.interests,
            evidence=extraction_result.evidence,
            recent_activity=self._recent_activity(events, window_start),
            signal_strength=min(
                total_decayed_signal / behavior_scoring_config.trigger_score_threshold,
                1.0,
            ),
            generated_at=reference_time,
            trigger=RecommendationTrigger(
                recommendation_refresh=False,
                reason=RecommendationTriggerReason.INSUFFICIENT_SIGNAL,
            ),
        )
        return profile.model_copy(
            update={
                "trigger": evaluate_recommendation_trigger(
                    profile,
                    reference_time=reference_time,
                    last_recommendation_at=last_recommendation_at,
                )
            }
        )

    def _product_context(
        self,
        resource_id: str | None,
        cache: dict[str, ProductInterestContext | None],
    ) -> ProductInterestContext | None:
        """Resolve only the product fields required by interest extraction."""
        if resource_id is None:
            return None
        if resource_id not in cache:
            try:
                product_id = UUID(resource_id)
            except ValueError:
                cache[resource_id] = None
            else:
                product = self.product_repository.get_by_id(product_id)
                cache[resource_id] = (
                    ProductInterestContext(title=product.title, category=product.category)
                    if product is not None
                    else None
                )
        return cache[resource_id]

    @staticmethod
    def _search_query(metadata: object) -> str | None:
        """Extract a usable historical search query without revalidating ingestion."""
        if not isinstance(metadata, dict):
            return None
        query = metadata.get("query")
        return query if isinstance(query, str) and query.strip() else None

    @staticmethod
    def _recent_activity(
        events: list[object], window_start: datetime
    ) -> RecentActivitySummary:
        """Summarize activity already loaded inside the profile time window."""
        total_events = len(events)
        product_views = sum(event.event_type is EventType.PRODUCT_VIEW for event in events)
        searches = sum(event.event_type is EventType.SEARCH for event in events)
        clicks = sum(event.event_type is EventType.CLICK for event in events)
        time_spent_seconds = sum(
            float(event.event_metadata["duration"])
            for event in events
            if event.event_type is EventType.TIME_SPENT
            and isinstance(event.event_metadata, dict)
            and isinstance(event.event_metadata.get("duration"), (int, float))
            and not isinstance(event.event_metadata.get("duration"), bool)
            and event.event_metadata["duration"] >= 0
        )

        return RecentActivitySummary(
            total_events=total_events,
            product_views=product_views,
            searches=searches,
            clicks=clicks,
            time_spent_seconds=time_spent_seconds,
            latest_event_at=events[-1].event_timestamp if events else None,
            window_start=window_start,
        )
