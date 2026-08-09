"""Application orchestration for generating persisted recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.ai.retrieval.retriever import SemanticProductRetrievalService
from app.models.recommendation import Recommendation
from app.repositories.recommendation import RecommendationRepository
from app.schemas.behavior import BehavioralProfile
from app.services.behavior import BehaviorProfileService


class RecommendationGenerationStatus(str, Enum):
    """Normal outcomes of recommendation generation orchestration."""

    GENERATED = "generated"
    TRIGGER_NOT_MET = "trigger_not_met"
    NO_PRODUCTS = "no_products"


@dataclass(frozen=True)
class RecommendationGenerationResult:
    """The profile and normal outcome produced by one generation attempt."""

    status: RecommendationGenerationStatus
    profile: BehavioralProfile
    recommendation: Recommendation | None = None


class RecommendationGenerationError(RuntimeError):
    """Raised when a completed graph invocation has no recommendation output."""


class RecommendationService:
    """Coordinate trigger, retrieval, graph generation, and recommendation persistence."""

    def __init__(
        self,
        behavior_profile_service: BehaviorProfileService,
        semantic_retrieval_service: SemanticProductRetrievalService,
        recommendation_repository: RecommendationRepository,
        recommendation_graph: Any,
    ) -> None:
        self.behavior_profile_service = behavior_profile_service
        self.semantic_retrieval_service = semantic_retrieval_service
        self.recommendation_repository = recommendation_repository
        self.recommendation_graph = recommendation_graph

    def get_latest_for_user(self, user_id: UUID) -> Recommendation | None:
        """Return the most recent persisted recommendation for one user."""
        return self.recommendation_repository.get_latest_for_user(user_id)

    def generate_for_user(
        self,
        user_id: UUID,
        *,
        reference_time: datetime | None = None,
    ) -> RecommendationGenerationResult:
        """Generate and persist a recommendation only when trigger and retrieval permit it."""
        last_recommendation_at = self.recommendation_repository.get_latest_created_at_for_user(
            user_id
        )
        profile = self.behavior_profile_service.generate_profile(
            user_id=user_id,
            reference_time=reference_time,
            last_recommendation_at=last_recommendation_at,
        )
        if not profile.trigger.recommendation_refresh:
            return RecommendationGenerationResult(
                status=RecommendationGenerationStatus.TRIGGER_NOT_MET,
                profile=profile,
            )

        retrieved_products = self.semantic_retrieval_service.retrieve(profile)
        if not retrieved_products:
            return RecommendationGenerationResult(
                status=RecommendationGenerationStatus.NO_PRODUCTS,
                profile=profile,
            )

        graph_state = self.recommendation_graph.invoke(
            {
                "profile": profile,
                "retrieved_products": retrieved_products,
                "generated_recommendation": None,
                "failure": None,
            }
        )
        generated_recommendation = graph_state.get("generated_recommendation")
        if generated_recommendation is None:
            raise RecommendationGenerationError(
                "Recommendation graph completed without a generated recommendation"
            )

        try:
            recommendation = self.recommendation_repository.create_for_user(
                user_id,
                generated_recommendation,
            )
            self.recommendation_repository.session.commit()
        except Exception:
            self.recommendation_repository.session.rollback()
            raise

        return RecommendationGenerationResult(
            status=RecommendationGenerationStatus.GENERATED,
            profile=profile,
            recommendation=recommendation,
        )
