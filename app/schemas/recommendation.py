"""Provider-independent recommendation generation contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecommendedProduct(BaseModel):
    """One catalog product selected by a recommendation generator."""

    product_id: UUID
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Reject text that is technically non-empty but has no content."""
        if not value.strip():
            raise ValueError("reason must not be blank")
        return value


class GeneratedRecommendation(BaseModel):
    """Structured recommendation output before catalog-grounding validation."""

    narrative: str = Field(min_length=1)
    recommendations: list[RecommendedProduct] = Field(min_length=1)

    @field_validator("narrative")
    @classmethod
    def validate_narrative(cls, value: str) -> str:
        """Reject text that is technically non-empty but has no content."""
        if not value.strip():
            raise ValueError("narrative must not be blank")
        return value

    @model_validator(mode="after")
    def validate_distinct_product_ids(self) -> "GeneratedRecommendation":
        """Require each selected catalog product to appear only once."""
        product_ids = [recommendation.product_id for recommendation in self.recommendations]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("recommendations must not contain duplicate product IDs")
        return self


class RecommendationProductResponse(BaseModel):
    """One persisted, ordered catalog selection in an API response."""

    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    reason: str
    position: int


class RecommendationResponse(BaseModel):
    """A persisted recommendation available to its owning user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    narrative: str
    created_at: datetime
    products: list[RecommendationProductResponse]


class RecommendationGenerationResponse(BaseModel):
    """The normal outcome of an authenticated generation attempt."""

    status: str
    recommendation: RecommendationResponse | None = None
