"""Nodes for the minimal recommendation-generation graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.agent.prompts import build_recommendation_prompt
from app.ai.agent.state import RecommendationAgentState
from app.ai.mesh.client import MeshRecommendationClient
from app.schemas.recommendation import GeneratedRecommendation


class RecommendationWorkflowError(RuntimeError):
    """Raised when a recommendation graph receives unusable input state."""


class RecommendationGroundingError(RecommendationWorkflowError):
    """Raised when generated product selections are absent from catalog candidates."""


def prepare_recommendation_context(
    state: RecommendationAgentState,
) -> dict[str, object]:
    """Verify the frozen upstream inputs needed for recommendation generation."""
    if "profile" not in state or state["profile"] is None:
        raise RecommendationWorkflowError("Recommendation graph requires a behavioral profile")
    if "retrieved_products" not in state or not state["retrieved_products"]:
        raise RecommendationWorkflowError(
            "Recommendation graph requires at least one retrieved product"
        )
    return {}


def build_generate_recommendation_node(
    client: MeshRecommendationClient,
) -> Callable[[RecommendationAgentState], dict[str, Any]]:
    """Bind the Mesh recommendation client as an explicit graph dependency."""

    def generate_recommendation(state: RecommendationAgentState) -> dict[str, Any]:
        prompt = build_recommendation_prompt(
            state["profile"],
            state["retrieved_products"],
        )
        recommendation: GeneratedRecommendation = client.generate(prompt)
        return {"generated_recommendation": recommendation, "failure": None}

    return generate_recommendation


def validate_recommendation_grounding(
    state: RecommendationAgentState,
) -> dict[str, object]:
    """Require every generated product ID to be present in the retrieved candidate set."""
    generated_recommendation = state.get("generated_recommendation")
    if generated_recommendation is None:
        raise RecommendationGroundingError(
            "Recommendation grounding requires a generated recommendation"
        )

    allowed_product_ids = {product.product_id for product in state["retrieved_products"]}
    invalid_product_ids = [
        selection.product_id
        for selection in generated_recommendation.recommendations
        if selection.product_id not in allowed_product_ids
    ]
    if invalid_product_ids:
        invalid_ids = ", ".join(str(product_id) for product_id in invalid_product_ids)
        raise RecommendationGroundingError(
            f"Recommendation catalog grounding failed for product IDs: {invalid_ids}"
        )
    return {}
