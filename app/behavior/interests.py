"""Deterministic interest extraction from decayed behavioral signals."""

from __future__ import annotations

from collections.abc import Iterable

from app.behavior.config import BehaviorScoringConfig, behavior_scoring_config
from app.models.event import EventType
from app.schemas.behavior import (
    BehaviorEvidence,
    InterestExtractionInput,
    InterestExtractionResult,
    InterestScore,
)


def _humanize_interest(value: str) -> str:
    """Collapse excess whitespace while preserving the original label casing."""
    return " ".join(value.split())


def _canonicalize_interest(value: str) -> str:
    """Create a deterministic aggregation key for an interest label."""
    return _humanize_interest(value).casefold()


def extract_interests(
    inputs: Iterable[InterestExtractionInput],
    config: BehaviorScoringConfig = behavior_scoring_config,
) -> InterestExtractionResult:
    """Extract, aggregate, normalize, and rank deterministic user interests.

    Scores are normalized before applying ``minimum_interest_score``; the
    remaining interests are ranked and then capped by ``max_interests``.
    """
    aggregated: dict[str, tuple[str, float]] = {}
    evidence: list[BehaviorEvidence] = []

    for extraction_input in inputs:
        signal = extraction_input.signal
        candidates: list[tuple[str, float, str]] = []

        if signal.event_type is EventType.SEARCH:
            if extraction_input.search_query is not None:
                candidates.append(
                    (
                        extraction_input.search_query,
                        config.search_interest_multiplier,
                        "search",
                    )
                )
        elif extraction_input.product is not None:
            candidates.extend(
                [
                    (
                        extraction_input.product.category,
                        config.product_category_multiplier,
                        "product_category",
                    ),
                    (
                        extraction_input.product.title,
                        config.product_title_multiplier,
                        "product_title",
                    ),
                ]
            )

        for interest, multiplier, source in candidates:
            label = _humanize_interest(interest)
            canonical_interest = _canonicalize_interest(interest)
            if not canonical_interest:
                continue

            contribution = signal.decayed_value * multiplier
            existing_label, existing_score = aggregated.get(
                canonical_interest, (label, 0.0)
            )
            aggregated[canonical_interest] = (
                existing_label,
                existing_score + contribution,
            )
            evidence.append(
                BehaviorEvidence(
                    interest=existing_label,
                    event_type=signal.event_type,
                    source=source,
                    contribution=contribution,
                    occurred_at=signal.occurred_at,
                )
            )

    if not aggregated:
        return InterestExtractionResult(interests=[], evidence=[])

    max_raw_score = max(raw_score for _, raw_score in aggregated.values())
    interests = [
        InterestScore(
            interest=label,
            score=raw_score / max_raw_score if max_raw_score else 0.0,
            raw_score=raw_score,
        )
        for _, (label, raw_score) in aggregated.items()
    ]
    interests = [
        interest
        for interest in interests
        if interest.score >= config.minimum_interest_score
    ]
    interests.sort(key=lambda interest: (-interest.score, interest.interest.casefold()))

    return InterestExtractionResult(
        interests=interests[: config.max_interests],
        evidence=evidence,
    )
