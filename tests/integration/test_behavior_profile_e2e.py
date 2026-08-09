"""End-to-end verification of persisted events producing a behavior profile."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.event import Event, EventType
from app.models.product import Product
from app.models.user import User
from app.repositories.event import EventRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.schemas.behavior import RecommendationTriggerReason
from app.services.behavior import BehaviorProfileService


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _product(title: str) -> Product:
    """Build a realistic persisted catalog product for the E2E scenario."""
    return Product(
        title=title,
        description="Enterprise course material for applied AI systems.",
        category="Agentic AI",
        price=Decimal("99.00"),
    )


def test_persisted_behavior_history_generates_a_ranked_profile(
    db_session: Session,
) -> None:
    """Verify the full repository-to-profile behavior intelligence path."""
    user = UserRepository(db_session).create(
        User(
            email="behavior-e2e@example.com",
            hashed_password="hashed-password",
            full_name="Behavior E2E User",
        )
    )
    product_repository = ProductRepository(db_session)
    product_a = product_repository.create(_product("Agentic AI Fundamentals"))
    product_b = product_repository.create(_product("Advanced LangGraph Agents"))

    event_repository = EventRepository(db_session)
    events = event_repository.create_many(
        [
            Event(
                user_id=user.id,
                session_id="behavior-e2e-session",
                event_type=EventType.PRODUCT_VIEW,
                resource_type="product",
                resource_id=str(product_a.id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=20),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="behavior-e2e-session",
                event_type=EventType.PRODUCT_VIEW,
                resource_type="product",
                resource_id=str(product_a.id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=18),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="behavior-e2e-session",
                event_type=EventType.SEARCH,
                event_timestamp=REFERENCE_TIME - timedelta(minutes=15),
                event_metadata={"query": "LangGraph"},
            ),
            Event(
                user_id=user.id,
                session_id="behavior-e2e-session",
                event_type=EventType.CLICK,
                resource_type="product",
                resource_id=str(product_b.id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=10),
                event_metadata={},
            ),
            Event(
                user_id=user.id,
                session_id="behavior-e2e-session",
                event_type=EventType.TIME_SPENT,
                resource_type="product",
                resource_id=str(product_b.id),
                event_timestamp=REFERENCE_TIME - timedelta(minutes=5),
                event_metadata={"duration": 180.0},
            ),
        ]
    )

    assert [event.id for event in event_repository.list_by_user(user.id)] == [
        event.id for event in events
    ]

    profile = BehaviorProfileService(
        event_repository, product_repository
    ).generate_profile(user.id, reference_time=REFERENCE_TIME)
    interests = {interest.interest: interest for interest in profile.interests}

    assert profile.user_id == user.id
    assert [interest.interest for interest in profile.interests] == [
        "Agentic AI",
        "LangGraph",
        "Advanced LangGraph Agents",
        "Agentic AI Fundamentals",
    ]
    assert interests["Agentic AI"].raw_score > interests["LangGraph"].raw_score
    assert interests["LangGraph"].raw_score > 0
    assert all(0.0 <= interest.score <= 1.0 for interest in profile.interests)
    assert profile.interests[0].score == pytest.approx(1.0)
    assert len(profile.evidence) == 9
    assert {evidence.source for evidence in profile.evidence} == {
        "search",
        "product_category",
        "product_title",
    }

    assert profile.recent_activity.total_events == 5
    assert profile.recent_activity.product_views == 2
    assert profile.recent_activity.searches == 1
    assert profile.recent_activity.clicks == 1
    assert profile.recent_activity.time_spent_seconds == pytest.approx(180.0)
    assert profile.recent_activity.latest_event_at == REFERENCE_TIME - timedelta(minutes=5)
    assert 0.0 <= profile.signal_strength <= 1.0
    assert profile.signal_strength == pytest.approx(1.0)
    assert profile.trigger.recommendation_refresh is True
    assert profile.trigger.reason is RecommendationTriggerReason.SEARCH_INTENT
