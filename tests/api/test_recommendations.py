"""API tests for authenticated recommendation generation and display."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.router import api_router
from app.api.v1.recommendations import (
    generate_recommendation,
    get_latest_recommendation,
    router,
)
from app.models.user import User
from app.services.recommendation_service import RecommendationGenerationStatus


def _user() -> User:
    return User(
        id=uuid4(),
        email="recommendations@example.com",
        hashed_password="hash",
        full_name="Recommendations",
        is_active=True,
    )


def _recommendation(user_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        narrative="These options fit your recent activity.",
        created_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        products=[
            SimpleNamespace(
                product_id=uuid4(),
                reason="Matches your demonstrated interest.",
                position=0,
            )
        ],
    )


def test_generate_recommendation_delegates_to_the_authenticated_users_service() -> None:
    user = _user()
    recommendation = _recommendation(user.id)
    service = SimpleNamespace(
        generate_for_user=lambda user_id: SimpleNamespace(
            status=RecommendationGenerationStatus.GENERATED,
            recommendation=recommendation,
        )
    )

    response = generate_recommendation(user, service)

    assert response.status == "generated"
    assert response.recommendation is not None
    assert response.recommendation.id == recommendation.id
    assert response.recommendation.products[0].product_id == recommendation.products[0].product_id


@pytest.mark.parametrize(
    "outcome",
    [
        RecommendationGenerationStatus.TRIGGER_NOT_MET,
        RecommendationGenerationStatus.NO_PRODUCTS,
    ],
)
def test_generate_recommendation_returns_normal_non_generation_outcomes(outcome) -> None:
    user = _user()
    service = SimpleNamespace(
        generate_for_user=lambda user_id: SimpleNamespace(status=outcome, recommendation=None)
    )

    response = generate_recommendation(user, service)

    assert response.status == outcome.value
    assert response.recommendation is None


def test_get_latest_recommendation_is_scoped_to_the_authenticated_user() -> None:
    user = _user()
    recommendation = _recommendation(user.id)
    requested_user_ids = []

    def get_latest_for_user(user_id):
        requested_user_ids.append(user_id)
        return recommendation

    response = get_latest_recommendation(user, SimpleNamespace(get_latest_for_user=get_latest_for_user))

    assert requested_user_ids == [user.id]
    assert response.id == recommendation.id


def test_get_latest_recommendation_returns_not_found_when_none_is_persisted() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_latest_recommendation(_user(), SimpleNamespace(get_latest_for_user=lambda user_id: None))

    assert exc_info.value.status_code == 404


def test_recommendation_router_is_registered_under_the_versioned_api_router() -> None:
    assert router.prefix == "/recommendations"
    assert [route.path for route in router.routes] == [
        "/recommendations/generate",
        "/recommendations/latest",
    ]
    assert any(getattr(route, "original_router", None) is router for route in api_router.routes)
