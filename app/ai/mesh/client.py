"""Mesh chat boundary for structured recommendation generation."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from langsmith import traceable

from app.ai.agent.prompts import RecommendationPrompt
from app.schemas.recommendation import GeneratedRecommendation
from meshapi import ChatCompletionParams, ChatMessage, MeshAPI


class MeshRecommendationClientError(RuntimeError):
    """Raised when Mesh chat cannot produce a valid recommendation contract."""


class MeshRecommendationClient:
    """Generate validated recommendation output through the selected Mesh chat model."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key and client is None:
            raise ValueError("MESH_API_KEY must be configured to generate recommendations")
        self.model = model
        self.client = client or MeshAPI(
            base_url="https://api.meshapi.ai",
            token=api_key,
        )

    @traceable(run_type="llm", name="mesh_recommendation_completion")
    def generate(self, prompt: RecommendationPrompt) -> GeneratedRecommendation:
        """Request schema-constrained JSON and validate it independently with Pydantic."""
        try:
            response = self.client.chat.completions.create(
                ChatCompletionParams(
                    model=self.model,
                    messages=[
                        ChatMessage(role="system", content=prompt.system),
                        ChatMessage(role="user", content=prompt.user),
                    ],
                    response_format=_recommendation_response_format(),
                )
            )
        except Exception as exc:
            raise MeshRecommendationClientError("Mesh recommendation request failed") from exc

        choices = getattr(response, "choices", None)
        if not choices:
            raise MeshRecommendationClientError("Mesh recommendation response contained no choices")
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise MeshRecommendationClientError(
                "Mesh recommendation response contained no message content"
            )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise MeshRecommendationClientError(
                "Mesh recommendation response was not valid JSON"
            ) from exc

        try:
            return GeneratedRecommendation.model_validate(payload)
        except ValidationError as exc:
            raise MeshRecommendationClientError(
                "Mesh recommendation response did not match the recommendation schema"
            ) from exc


def _recommendation_response_format() -> dict[str, object]:
    """Return Mesh's JSON-schema response format from the authoritative Pydantic model."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "generated_recommendation",
            "schema": GeneratedRecommendation.model_json_schema(),
        },
    }
