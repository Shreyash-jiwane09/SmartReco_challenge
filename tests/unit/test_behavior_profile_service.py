"""Tests for deterministic behavioral profile orchestration."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.models.event import Event, EventType
from app.models.product import Product
from app.schemas.behavior import RecommendationTriggerReason
from app.services.behavior import BehaviorProfileService


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


class FakeEventRepository:
    def __init__(self, events: list[Event]) -> None:
        self.events = events
        self.calls: list[tuple[UUID, datetime, datetime]] = []

    def list_by_user_time_range(
        self, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[Event]:
        self.calls.append((user_id, start_time, end_time))
        return [
            event
            for event in self.events
            if event.user_id == user_id and start_time <= event.event_timestamp <= end_time
        ]


class FakeProductRepository:
    def __init__(self, products: dict[UUID, Product]) -> None:
        self.products = products
        self.calls: list[UUID] = []

    def get_by_id(self, product_id: UUID) -> Product | None:
        self.calls.append(product_id)
        return self.products.get(product_id)


def _event(
    user_id: UUID,
    event_type: EventType,
    timestamp: datetime,
    *,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> Event:
    return Event(
        id=uuid4(),
        user_id=user_id,
        session_id="session-1",
        event_type=event_type,
        resource_type="product" if resource_id else None,
        resource_id=resource_id,
        event_timestamp=timestamp,
        event_metadata=metadata or {},
    )


def _product(product_id: UUID) -> Product:
    return Product(
        id=product_id,
        title="Trail Runner",
        description="A durable shoe",
        category="Footwear",
        price=Decimal("99.00"),
    )


def _service(events: list[Event], products: dict[UUID, Product] | None = None) -> tuple:
    event_repository = FakeEventRepository(events)
    product_repository = FakeProductRepository(products or {})
    return BehaviorProfileService(event_repository, product_repository), event_repository, product_repository


def test_empty_history_returns_a_valid_empty_profile() -> None:
    user_id = uuid4()
    service, event_repository, _ = _service([])

    profile = service.generate_profile(user_id, REFERENCE_TIME)

    assert profile.interests == []
    assert profile.evidence == []
    assert profile.recent_activity.total_events == 0
    assert profile.recent_activity.latest_event_at is None
    assert profile.signal_strength == 0.0
    assert profile.trigger.recommendation_refresh is False
    assert profile.trigger.reason is RecommendationTriggerReason.INSUFFICIENT_SIGNAL
    assert event_repository.calls[0][1] == REFERENCE_TIME - timedelta(days=30)


def test_search_history_is_decayed_and_accumulated_into_ranked_interest() -> None:
    user_id = uuid4()
    events = [
        _event(user_id, EventType.SEARCH, REFERENCE_TIME, metadata={"query": "boots"}),
        _event(
            user_id,
            EventType.SEARCH,
            REFERENCE_TIME - timedelta(hours=72),
            metadata={"query": "boots"},
        ),
    ]
    service, _, _ = _service(events)

    profile = service.generate_profile(user_id, REFERENCE_TIME)

    assert profile.interests[0].interest == "boots"
    assert profile.interests[0].raw_score == pytest.approx(6.0)
    assert profile.signal_strength == pytest.approx(1.0)


def test_product_events_resolve_context_once_and_accumulate_interests() -> None:
    user_id = uuid4()
    product_id = uuid4()
    events = [
        _event(user_id, EventType.PRODUCT_VIEW, REFERENCE_TIME, resource_id=str(product_id)),
        _event(user_id, EventType.CLICK, REFERENCE_TIME, resource_id=str(product_id)),
    ]
    service, _, product_repository = _service(events, {product_id: _product(product_id)})

    profile = service.generate_profile(user_id, REFERENCE_TIME)
    interests = {interest.interest: interest.raw_score for interest in profile.interests}

    assert interests == {"Footwear": pytest.approx(3.0), "Trail Runner": pytest.approx(1.5)}
    assert product_repository.calls == [product_id]


def test_recent_activity_summarizes_events_and_valid_time_spent_duration() -> None:
    user_id = uuid4()
    events = [
        _event(user_id, EventType.PRODUCT_VIEW, REFERENCE_TIME - timedelta(hours=4)),
        _event(user_id, EventType.SEARCH, REFERENCE_TIME - timedelta(hours=3), metadata={"query": "boots"}),
        _event(user_id, EventType.CLICK, REFERENCE_TIME - timedelta(hours=2)),
        _event(
            user_id,
            EventType.TIME_SPENT,
            REFERENCE_TIME - timedelta(hours=1),
            metadata={"duration": 12.5},
        ),
    ]
    service, _, _ = _service(events)

    profile = service.generate_profile(user_id, REFERENCE_TIME)

    assert profile.recent_activity.total_events == 4
    assert profile.recent_activity.product_views == 1
    assert profile.recent_activity.searches == 1
    assert profile.recent_activity.clicks == 1
    assert profile.recent_activity.time_spent_seconds == pytest.approx(12.5)
    assert profile.recent_activity.latest_event_at == REFERENCE_TIME - timedelta(hours=1)


def test_events_outside_window_are_excluded_and_reference_time_is_deterministic() -> None:
    user_id = uuid4()
    recent = _event(user_id, EventType.SEARCH, REFERENCE_TIME, metadata={"query": "boots"})
    old = _event(
        user_id,
        EventType.SEARCH,
        REFERENCE_TIME - timedelta(days=31),
        metadata={"query": "old boots"},
    )
    service, _, _ = _service([old, recent])

    first = service.generate_profile(user_id, REFERENCE_TIME)
    second = service.generate_profile(user_id, REFERENCE_TIME)

    assert [interest.interest for interest in first.interests] == ["boots"]
    assert first == second
    assert first.generated_at == REFERENCE_TIME


def test_missing_product_does_not_prevent_signal_strength_from_being_calculated() -> None:
    user_id = uuid4()
    service, _, _ = _service(
        [_event(user_id, EventType.CLICK, REFERENCE_TIME, resource_id=str(uuid4()))]
    )

    profile = service.generate_profile(user_id, REFERENCE_TIME)

    assert profile.interests == []
    assert profile.signal_strength == pytest.approx(0.4)


def test_stronger_history_has_greater_signal_strength_than_weaker_history() -> None:
    user_id = uuid4()
    weak_service, _, _ = _service(
        [_event(user_id, EventType.PRODUCT_VIEW, REFERENCE_TIME)]
    )
    strong_service, _, _ = _service(
        [_event(user_id, EventType.SEARCH, REFERENCE_TIME, metadata={"query": "boots"})]
    )

    assert (
        strong_service.generate_profile(user_id, REFERENCE_TIME).signal_strength
        >= weak_service.generate_profile(user_id, REFERENCE_TIME).signal_strength
    )
