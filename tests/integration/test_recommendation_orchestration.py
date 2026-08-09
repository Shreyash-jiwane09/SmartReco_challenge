"""PostgreSQL integration tests for recommendation generation orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.retrieval.retriever import RetrievedProduct
from app.models.product import Product
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.user import UserRepository
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)
from app.schemas.recommendation import GeneratedRecommendation, RecommendedProduct
from app.services.recommendation_service import (
    RecommendationGenerationStatus,
    RecommendationService,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


class _BehaviorProfileService:
    def __init__(self, profile: BehavioralProfile) -> None:
        self.profile = profile

    def generate_profile(self, **_kwargs: object) -> BehavioralProfile:
        return self.profile


class _RetrievalService:
    def __init__(self, products: list[RetrievedProduct]) -> None:
        self.products = products
        self.calls = 0

    def retrieve(self, _profile: BehavioralProfile) -> list[RetrievedProduct]:
        self.calls += 1
        return self.products


class _Graph:
    def __init__(self, generated: GeneratedRecommendation) -> None:
        self.generated = generated
        self.calls = 0

    def invoke(self, _state: dict[str, object]) -> dict[str, object]:
        self.calls += 1
        return {"generated_recommendation": self.generated}


def _profile(*, refresh: bool) -> BehavioralProfile:
    return BehavioralProfile(
        user_id=uuid4(),
        interests=[InterestScore(interest="Agentic AI", score=1.0, raw_score=4.0)],
        evidence=[],
        recent_activity=RecentActivitySummary(
            total_events=1,
            product_views=1,
            searches=0,
            clicks=0,
            time_spent_seconds=0.0,
            latest_event_at=REFERENCE_TIME,
            window_start=REFERENCE_TIME,
        ),
        signal_strength=1.0,
        generated_at=REFERENCE_TIME,
        trigger=RecommendationTrigger(
            recommendation_refresh=refresh,
            reason=(
                RecommendationTriggerReason.SEARCH_INTENT
                if refresh
                else RecommendationTriggerReason.INSUFFICIENT_SIGNAL
            ),
        ),
    )


def _product(title: str) -> Product:
    return Product(
        title=title,
        description=f"Description for {title}",
        category="AI",
        price=Decimal("79.00"),
    )


def test_service_persists_generated_recommendation_with_real_postgresql(
    db_session: Session,
) -> None:
    user = UserRepository(db_session).create(
        User(
            email="orchestration@example.com",
            hashed_password="hash",
            full_name="Orchestration User",
        )
    )
    product = ProductRepository(db_session).create(_product("Agentic AI Fundamentals"))
    db_session.commit()
    retrieved = RetrievedProduct(
        product_id=product.id,
        title=product.title,
        description=product.description,
        category=product.category,
        price=product.price,
        distance=0.1,
    )
    generated = GeneratedRecommendation(
        narrative="A tailored learning path.",
        recommendations=[
            RecommendedProduct(product_id=product.id, reason="Matches your agentic AI interest.")
        ],
    )
    repository = RecommendationRepository(db_session)
    service = RecommendationService(
        _BehaviorProfileService(_profile(refresh=True)),  # type: ignore[arg-type]
        _RetrievalService([retrieved]),  # type: ignore[arg-type]
        repository,
        _Graph(generated),
    )

    result = service.generate_for_user(user.id, reference_time=REFERENCE_TIME)
    persisted = repository.get_latest_for_user(user.id)

    assert result.status is RecommendationGenerationStatus.GENERATED
    assert persisted is not None
    assert persisted.id == result.recommendation.id
    assert persisted.narrative == generated.narrative
    assert [item.product_id for item in persisted.products] == [product.id]
    assert [item.reason for item in persisted.products] == [
        "Matches your agentic AI interest."
    ]
    assert repository.get_latest_created_at_for_user(user.id) == persisted.created_at


def test_service_trigger_false_does_not_insert_recommendation(
    db_session: Session,
) -> None:
    user = UserRepository(db_session).create(
        User(
            email="orchestration-skip@example.com",
            hashed_password="hash",
            full_name="Orchestration Skip User",
        )
    )
    db_session.commit()
    repository = RecommendationRepository(db_session)
    retrieval = _RetrievalService([])
    graph = _Graph(
        GeneratedRecommendation(
            narrative="Unused.",
            recommendations=[RecommendedProduct(product_id=uuid4(), reason="Unused.")],
        )
    )
    service = RecommendationService(
        _BehaviorProfileService(_profile(refresh=False)),  # type: ignore[arg-type]
        retrieval,  # type: ignore[arg-type]
        repository,
        graph,
    )

    result = service.generate_for_user(user.id)

    assert result.status is RecommendationGenerationStatus.TRIGGER_NOT_MET
    assert retrieval.calls == 0
    assert graph.calls == 0
    assert repository.get_latest_for_user(user.id) is None
