"""Authenticated recommendation generation and display endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_recommendation_service
from app.models.user import User
from app.schemas.recommendation import (
    RecommendationGenerationResponse,
    RecommendationResponse,
)
from app.services.recommendation_service import RecommendationService


router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post("/generate", response_model=RecommendationGenerationResponse)
def generate_recommendation(
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationGenerationResponse:
    """Generate a recommendation for the authenticated user when eligible."""
    result = service.generate_for_user(current_user.id)
    return RecommendationGenerationResponse(
        status=result.status.value,
        recommendation=(
            RecommendationResponse.model_validate(result.recommendation)
            if result.recommendation is not None
            else None
        ),
    )


@router.get("/latest", response_model=RecommendationResponse)
def get_latest_recommendation(
    current_user: User = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    """Return the latest persisted recommendation for the authenticated user."""
    recommendation = service.get_latest_for_user(current_user.id)
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No recommendation found for the authenticated user",
        )
    return RecommendationResponse.model_validate(recommendation)
