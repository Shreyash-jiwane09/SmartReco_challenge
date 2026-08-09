"""Tests for the Mesh recommendation chat boundary."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.agent.prompts import RecommendationPrompt
from app.ai.mesh.client import MeshRecommendationClient, MeshRecommendationClientError
from app.schemas.recommendation import GeneratedRecommendation


class _FakeMeshClient:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[object] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, params: object) -> object:
        self.calls.append(params)
        if self.error is not None:
            raise self.error
        return self.response


def _prompt() -> RecommendationPrompt:
    return RecommendationPrompt(system="system instructions", user="catalog context")


def _response(content: object) -> object:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_client_sends_configured_model_messages_and_json_schema_format() -> None:
    product_id = uuid4()
    fake_client = _FakeMeshClient(
        _response(
            '{"narrative":"A tailored course.","recommendations":['
            f'{{"product_id":"{product_id}","reason":"Matches your interests."}}]}}'
        )
    )
    client = MeshRecommendationClient(
        api_key="test-key",
        model="openai/gpt-4o-mini",
        client=fake_client,
    )

    result = client.generate(_prompt())
    params = fake_client.calls[0]

    assert isinstance(result, GeneratedRecommendation)
    assert params.model == "openai/gpt-4o-mini"
    assert [(message.role, message.content) for message in params.messages] == [
        ("system", "system instructions"),
        ("user", "catalog context"),
    ]
    assert params.response_format["type"] == "json_schema"
    assert params.response_format["json_schema"]["name"] == "generated_recommendation"
    assert "strict" not in params.response_format["json_schema"]
    assert params.response_format["json_schema"]["schema"] == (
        GeneratedRecommendation.model_json_schema()
    )


def test_client_rejects_malformed_json() -> None:
    client = MeshRecommendationClient(
        api_key="test-key", model="test-model", client=_FakeMeshClient(_response("not json"))
    )

    with pytest.raises(MeshRecommendationClientError, match="not valid JSON"):
        client.generate(_prompt())


def test_client_rejects_structurally_invalid_recommendation() -> None:
    client = MeshRecommendationClient(
        api_key="test-key",
        model="test-model",
        client=_FakeMeshClient(_response('{"narrative":"Missing recommendations."}')),
    )

    with pytest.raises(MeshRecommendationClientError, match="did not match"):
        client.generate(_prompt())


def test_client_rejects_empty_choices() -> None:
    client = MeshRecommendationClient(
        api_key="test-key", model="test-model", client=_FakeMeshClient(SimpleNamespace(choices=[]))
    )

    with pytest.raises(MeshRecommendationClientError, match="no choices"):
        client.generate(_prompt())


@pytest.mark.parametrize("content", [None, "", "   "])
def test_client_rejects_empty_message_content(content: object) -> None:
    client = MeshRecommendationClient(
        api_key="test-key", model="test-model", client=_FakeMeshClient(_response(content))
    )

    with pytest.raises(MeshRecommendationClientError, match="no message content"):
        client.generate(_prompt())


def test_client_wraps_mesh_request_failure() -> None:
    client = MeshRecommendationClient(
        api_key="test-key",
        model="test-model",
        client=_FakeMeshClient(error=RuntimeError("provider unavailable")),
    )

    with pytest.raises(MeshRecommendationClientError, match="request failed") as exc_info:
        client.generate(_prompt())

    assert isinstance(exc_info.value.__cause__, RuntimeError)
