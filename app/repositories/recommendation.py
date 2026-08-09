"""Repository operations for persisted recommendations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.recommendation import Recommendation, RecommendationProduct
from app.repositories.base import BaseRepository
from app.schemas.recommendation import GeneratedRecommendation


class RecommendationRepository(BaseRepository[Recommendation]):
    """Persist and retrieve already-grounded recommendation results."""

    def __init__(self, session: Session) -> None:
        super().__init__(Recommendation, session)

    def create_for_user(
        self,
        user_id: UUID,
        generated_recommendation: GeneratedRecommendation,
    ) -> Recommendation:
        """Add one ordered recommendation and its selected Product references without commit."""
        recommendation = Recommendation(
            user_id=user_id,
            narrative=generated_recommendation.narrative,
            products=[
                RecommendationProduct(
                    product_id=selection.product_id,
                    reason=selection.reason,
                    position=position,
                )
                for position, selection in enumerate(generated_recommendation.recommendations)
            ],
        )
        return self.create(recommendation)

    def get_latest_for_user(self, user_id: UUID) -> Recommendation | None:
        """Return the newest recommendation for a user with ordered product selections."""
        statement = (
            select(Recommendation)
            .where(Recommendation.user_id == user_id)
            .options(selectinload(Recommendation.products))
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_latest_created_at_for_user(self, user_id: UUID) -> datetime | None:
        """Return the timestamp of a user's newest persisted recommendation."""
        statement = (
            select(Recommendation.created_at)
            .where(Recommendation.user_id == user_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()
