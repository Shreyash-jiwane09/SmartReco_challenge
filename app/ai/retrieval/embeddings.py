"""Mesh-backed embedding generation."""

from __future__ import annotations

from typing import Any

from meshapi import EmbeddingsParams, MeshAPI


class EmbeddingError(RuntimeError):
    """Raised when Mesh does not return a usable dense embedding."""


class MeshEmbeddingService:
    """Generate dense embeddings through the Mesh API."""

    def __init__(self, *, api_key: str, model: str, client: Any | None = None) -> None:
        if not api_key and client is None:
            raise ValueError("MESH_API_KEY must be configured to generate embeddings")
        self.model = model
        self.client = client or MeshAPI(
            base_url="https://api.meshapi.ai",
            token=api_key,
        )

    def embed(self, text: str) -> list[float]:
        """Return one dense embedding for text without exposing Mesh response types."""
        response = self.client.embeddings.create(
            EmbeddingsParams(model=self.model, input=text)
        )
        try:
            embedding = response.data[0].embedding
        except (AttributeError, IndexError, TypeError) as exc:
            raise EmbeddingError("Mesh returned no embedding data") from exc

        if not isinstance(embedding, (list, tuple)) or not embedding:
            raise EmbeddingError("Mesh returned an empty or malformed embedding")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in embedding):
            raise EmbeddingError("Mesh returned an embedding with non-numeric values")
        return [float(value) for value in embedding]
