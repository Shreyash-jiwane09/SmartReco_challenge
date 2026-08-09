"""Typed state shared by the future recommendation graph."""

from __future__ import annotations

from typing import TypedDict

from app.ai.retrieval.retriever import RetrievedProduct
from app.schemas.behavior import BehavioralProfile
from app.schemas.recommendation import GeneratedRecommendation


class RecommendationAgentState(TypedDict):
    """Explicit workflow data for catalog-grounded recommendation generation."""

    profile: BehavioralProfile
    retrieved_products: list[RetrievedProduct]
    generated_recommendation: GeneratedRecommendation | None
    failure: str | None
