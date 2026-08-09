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
