"""Minimal LangGraph workflow for recommendation generation."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.ai.agent.nodes import (
    build_generate_recommendation_node,
    prepare_recommendation_context,
    validate_recommendation_grounding,
)
from app.ai.agent.state import RecommendationAgentState
from app.ai.mesh.client import MeshRecommendationClient


def build_recommendation_graph(client: MeshRecommendationClient) -> Any:
    """Compile the prepare, generate, then catalog-ground workflow."""
    builder = StateGraph(RecommendationAgentState)
    builder.add_node("prepare_context", prepare_recommendation_context)
    builder.add_node(
        "generate_recommendation",
        build_generate_recommendation_node(client),
    )
    builder.add_node("validate_grounding", validate_recommendation_grounding)
    builder.add_edge(START, "prepare_context")
    builder.add_edge("prepare_context", "generate_recommendation")
    builder.add_edge("generate_recommendation", "validate_grounding")
    builder.add_edge("validate_grounding", END)
    return builder.compile()
