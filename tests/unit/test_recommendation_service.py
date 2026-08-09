"""Unit tests for recommendation generation orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.retrieval.retriever import RetrievedProduct
from app.models.event import EventType
from app.schemas.behavior import (
    BehavioralProfile,
    InterestScore,
    RecentActivitySummary,
    RecommendationTrigger,
    RecommendationTriggerReason,
)
from app.schemas.recommendation import GeneratedRecommendation, RecommendedProduct
from app.services.recommendation_service import (
    RecommendationGenerationError,
    RecommendationGenerationStatus,
    RecommendationService,
)


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


class _Session:
    def __init__(self, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.rollbacks += 1


class _RecommendationRepository:
    def __init__(
        self,
        calls: list[str],
        last_recommendation_at: datetime | None,
        session: _Session,
        create_error: Exception | None = None,
    ) -> None:
        self.calls = calls
        self.last_recommendation_at = last_recommendation_at
        self.session = session
        self.create_error = create_error
        self.created: list[tuple[object, GeneratedRecommendation]] = []

    def get_latest_created_at_for_user(self, user_id: object) -> datetime | None:
        self.calls.append("latest")
        return self.last_recommendation_at

    def create_for_user(self, user_id: object, generated: GeneratedRecommendation) -> object:
        self.calls.append("persist")
        if self.create_error is not None:
            raise self.create_error
        self.created.append((user_id, generated))
        return SimpleNamespace(id=uuid4(), user_id=user_id, narrative=generated.narrative)


class _BehaviorProfileService:
    def __init__(self, calls: list[str], profile: BehavioralProfile) -> None:
        self.calls = calls
        self.profile = profile
        self.arguments: dict[str, object] | None = None

    def generate_profile(self, **kwargs: object) -> BehavioralProfile:
        self.calls.append("profile")
        self.arguments = kwargs
        return self.profile


class _RetrievalService:
    def __init__(self, calls: list[str], products: list[RetrievedProduct]) -> None:
        self.calls = calls
        self.products = products
        self.profile: BehavioralProfile | None = None

    def retrieve(self, profile: BehavioralProfile) -> list[RetrievedProduct]:
        self.calls.append("retrieve")
        self.profile = profile
        return self.products


class _Graph:
    def __init__(self, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {}
        self.error = error
        self.calls: list[dict[str, object]] = []

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        self.calls.append(state)
        if self.error is not None:
            raise self.error
        return self.result


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


def _product() -> RetrievedProduct:
    return RetrievedProduct(
        product_id=uuid4(),
        title="Agentic AI Fundamentals",
        description="Learn practical agent workflows.",
        category="AI",
        price=Decimal("79.00"),
        distance=0.1,
    )


def _generated(product_id) -> GeneratedRecommendation:
    return GeneratedRecommendation(
        narrative="A tailored course for your agentic AI interests.",
        recommendations=[
            RecommendedProduct(product_id=product_id, reason="Matches your recent interest.")
        ],
    )


def _service(
    *,
    profile: BehavioralProfile,
    products: list[RetrievedProduct] | None = None,
    graph_result: dict[str, object] | None = None,
    graph_error: Exception | None = None,
    create_error: Exception | None = None,
    commit_error: Exception | None = None,
) -> tuple[RecommendationService, _RecommendationRepository, _BehaviorProfileService, _RetrievalService, _Graph, _Session, list[str]]:
    calls: list[str] = []
    session = _Session(commit_error)
    repository = _RecommendationRepository(calls, REFERENCE_TIME, session, create_error)
    behavior = _BehaviorProfileService(calls, profile)
    retrieval = _RetrievalService(calls, products or [])
    graph = _Graph(graph_result, graph_error)
    return (
        RecommendationService(behavior, retrieval, repository, graph),  # type: ignore[arg-type]
        repository,
        behavior,
        retrieval,
        graph,
        session,
        calls,
    )


def test_trigger_false_stops_before_retrieval_graph_persistence_and_commit() -> None:
    profile = _profile(refresh=False)
    service, repository, behavior, retrieval, graph, session, calls = _service(profile=profile)
    user_id = uuid4()

    result = service.generate_for_user(user_id, reference_time=REFERENCE_TIME)

    assert result.status is RecommendationGenerationStatus.TRIGGER_NOT_MET
    assert result.profile is profile
    assert result.recommendation is None
    assert calls == ["latest", "profile"]
    assert behavior.arguments == {
        "user_id": user_id,
        "reference_time": REFERENCE_TIME,
        "last_recommendation_at": REFERENCE_TIME,
    }
    assert retrieval.profile is None
    assert graph.calls == []
    assert repository.created == []
    assert session.commits == 0


def test_empty_retrieval_returns_normal_no_products_result() -> None:
    profile = _profile(refresh=True)
    service, repository, _, retrieval, graph, session, calls = _service(profile=profile)

    result = service.generate_for_user(uuid4())

    assert result.status is RecommendationGenerationStatus.NO_PRODUCTS
    assert calls == ["latest", "profile", "retrieve"]
    assert retrieval.profile is profile
    assert graph.calls == []
    assert repository.created == []
    assert session.commits == 0


def test_success_uses_same_profile_and_products_then_persists_and_commits() -> None:
    profile = _profile(refresh=True)
    product = _product()
    generated = _generated(product.product_id)
    service, repository, _, retrieval, graph, session, calls = _service(
        profile=profile,
        products=[product],
        graph_result={"generated_recommendation": generated},
    )
    user_id = uuid4()

    result = service.generate_for_user(user_id)

    assert result.status is RecommendationGenerationStatus.GENERATED
    assert result.recommendation is not None
    assert calls == ["latest", "profile", "retrieve", "persist"]
    assert retrieval.profile is profile
    assert graph.calls == [
        {
            "profile": profile,
            "retrieved_products": [product],
            "generated_recommendation": None,
            "failure": None,
        }
    ]
    assert repository.created == [(user_id, generated)]
    assert session.commits == 1
    assert session.rollbacks == 0


def test_graph_failure_propagates_without_persistence_or_commit() -> None:
    profile = _profile(refresh=True)
    service, repository, _, _, graph, session, _ = _service(
        profile=profile,
        products=[_product()],
        graph_error=RuntimeError("Mesh failure"),
    )

    with pytest.raises(RuntimeError, match="Mesh failure"):
        service.generate_for_user(uuid4())

    assert len(graph.calls) == 1
    assert repository.created == []
    assert session.commits == 0
    assert session.rollbacks == 0


def test_missing_graph_recommendation_fails_without_persistence() -> None:
    service, repository, _, _, _, session, _ = _service(
        profile=_profile(refresh=True),
        products=[_product()],
        graph_result={"generated_recommendation": None},
    )

    with pytest.raises(RecommendationGenerationError, match="without a generated recommendation"):
        service.generate_for_user(uuid4())

    assert repository.created == []
    assert session.commits == 0


@pytest.mark.parametrize("failure", [RuntimeError("database write failed"), RuntimeError("commit failed")])
def test_persistence_or_commit_failure_rolls_back_and_does_not_return_success(
    failure: RuntimeError,
) -> None:
    product = _product()
    service, repository, _, _, _, session, _ = _service(
        profile=_profile(refresh=True),
        products=[product],
        graph_result={"generated_recommendation": _generated(product.product_id)},
        create_error=failure if str(failure) == "database write failed" else None,
        commit_error=failure if str(failure) == "commit failed" else None,
    )

    with pytest.raises(RuntimeError, match=str(failure)):
        service.generate_for_user(uuid4())

    assert session.rollbacks == 1
    assert session.commits == (1 if str(failure) == "commit failed" else 0)
    assert len(repository.created) == (0 if str(failure) == "database write failed" else 1)
