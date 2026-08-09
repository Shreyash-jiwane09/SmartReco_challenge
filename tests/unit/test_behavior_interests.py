"""Tests for deterministic interest extraction and ranking."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.behavior.config import BehaviorScoringConfig
from app.behavior.interests import extract_interests
from app.models.event import EventType
from app.schemas.behavior import (
    DecayedBehaviorSignal,
    InterestExtractionInput,
    ProductInterestContext,
)


OCCURRED_AT = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _input(
    event_type: EventType,
    *,
    decayed_value: float = 4.0,
    search_query: str | None = None,
    product: ProductInterestContext | None = None,
) -> InterestExtractionInput:
    return InterestExtractionInput(
        signal=DecayedBehaviorSignal(
            event_id=uuid4(),
            user_id=uuid4(),
            event_type=event_type,
            base_weight=4.0,
            signal_value=4.0,
            source=event_type.value.lower(),
            occurred_at=OCCURRED_AT,
            resource_id="product-1",
            decay_factor=1.0,
            decayed_value=decayed_value,
        ),
        search_query=search_query,
        product=product,
    )


def _product(title: str = "Trail Runner", category: str = "Footwear") -> ProductInterestContext:
    return ProductInterestContext(title=title, category=category)


def test_search_produces_an_interest_from_its_query() -> None:
    result = extract_interests([_input(EventType.SEARCH, search_query="running shoes")])

    assert result.interests[0].interest == "running shoes"
    assert result.interests[0].raw_score == pytest.approx(4.0)
    assert result.evidence[0].source == "search"


def test_product_category_and_title_produce_configured_contributions() -> None:
    result = extract_interests([_input(EventType.PRODUCT_VIEW, product=_product())])
    interests = {interest.interest: interest for interest in result.interests}

    assert interests["Footwear"].raw_score == pytest.approx(4.0)
    assert interests["Trail Runner"].raw_score == pytest.approx(2.0)
    assert interests["Footwear"].raw_score > interests["Trail Runner"].raw_score


def test_repeated_canonical_interest_evidence_accumulates() -> None:
    result = extract_interests(
        [
            _input(EventType.SEARCH, decayed_value=2.0, search_query="LangGraph"),
            _input(EventType.SEARCH, decayed_value=3.0, search_query=" langgraph "),
        ]
    )

    assert len(result.interests) == 1
    assert result.interests[0].interest == "LangGraph"
    assert result.interests[0].raw_score == pytest.approx(5.0)
    assert len(result.evidence) == 2


def test_decayed_value_controls_the_raw_interest_score() -> None:
    result = extract_interests(
        [_input(EventType.SEARCH, decayed_value=1.25, search_query="hiking")]
    )

    assert result.interests[0].raw_score == pytest.approx(1.25)


def test_scores_are_normalized_relative_to_the_strongest_interest_and_ranked() -> None:
    result = extract_interests(
        [
            _input(EventType.SEARCH, decayed_value=4.0, search_query="boots"),
            _input(EventType.SEARCH, decayed_value=2.0, search_query="sandals"),
        ]
    )

    assert [interest.interest for interest in result.interests] == ["boots", "sandals"]
    assert result.interests[0].score == pytest.approx(1.0)
    assert result.interests[1].score == pytest.approx(0.5)


def test_empty_input_returns_empty_interests_and_evidence() -> None:
    assert extract_interests([]).interests == []
    assert extract_interests([]).evidence == []


def test_missing_product_context_produces_no_invented_interest() -> None:
    result = extract_interests([_input(EventType.CLICK)])

    assert result.interests == []
    assert result.evidence == []


def test_filtering_happens_after_normalization_and_before_max_limit() -> None:
    config = BehaviorScoringConfig(minimum_interest_score=0.6, max_interests=1)
    result = extract_interests(
        [
            _input(EventType.SEARCH, decayed_value=4.0, search_query="boots"),
            _input(EventType.SEARCH, decayed_value=2.0, search_query="sandals"),
            _input(EventType.SEARCH, decayed_value=3.0, search_query="hats"),
        ],
        config,
    )

    assert [interest.interest for interest in result.interests] == ["boots"]


def test_max_interests_is_respected_after_ranking() -> None:
    config = BehaviorScoringConfig(minimum_interest_score=0.0, max_interests=2)
    result = extract_interests(
        [
            _input(EventType.SEARCH, decayed_value=3.0, search_query="boots"),
            _input(EventType.SEARCH, decayed_value=2.0, search_query="hats"),
            _input(EventType.SEARCH, decayed_value=1.0, search_query="sandals"),
        ],
        config,
    )

    assert [interest.interest for interest in result.interests] == ["boots", "hats"]


def test_evidence_records_explain_each_product_contribution() -> None:
    result = extract_interests([_input(EventType.TIME_SPENT, product=_product())])

    assert [(item.source, item.contribution) for item in result.evidence] == [
        ("product_category", 4.0),
        ("product_title", 2.0),
    ]
