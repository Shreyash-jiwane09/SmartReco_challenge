"""Minimal LangGraph workflow for recommendation generation."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.ai.agent.nodes import (
    build_generate_recommendation_node,
    prepare_recommendation_context,
)
from app.ai.agent.state import RecommendationAgentState
from app.ai.mesh.client import MeshRecommendationClient


def build_recommendation_graph(client: MeshRecommendationClient) -> Any:
    """Compile the explicit prepare-context then generate-recommendation workflow."""
    builder = StateGraph(RecommendationAgentState)
    builder.add_node("prepare_context", prepare_recommendation_context)
    builder.add_node(
        "generate_recommendation",
        build_generate_recommendation_node(client),
    )
    builder.add_edge(START, "prepare_context")
    builder.add_edge("prepare_context", "generate_recommendation")
    builder.add_edge("generate_recommendation", END)
    return builder.compile()
