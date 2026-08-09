"""Persistent Chroma storage for Product vectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb


@dataclass(frozen=True)
class ProductVectorCandidate:
    """One ranked Product candidate returned by Chroma."""

    product_id: str
    distance: float


class ProductChromaStore:
    """Store explicitly generated Product embeddings in one Chroma collection."""

    def __init__(
        self,
        *,
        persist_directory: str,
        collection_name: str,
        client: Any | None = None,
    ) -> None:
        self.client = client or chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
        )

    def upsert_product(
        self,
        *,
        product_id: str,
        document: str,
        metadata: dict[str, Any],
        embedding: list[float],
    ) -> str:
        """Upsert one Product vector using its authoritative SQL UUID."""
        self.collection.upsert(
            ids=[product_id],
            documents=[document],
            metadatas=[metadata],
            embeddings=[embedding],
        )
        return product_id

    def delete_product(self, product_id: str) -> None:
        """Remove a Product vector by its authoritative SQL UUID."""
        self.collection.delete(ids=[product_id])

    def query_products(
        self,
        *,
        query_embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[ProductVectorCandidate]:
        """Return ranked Product IDs and raw Chroma distances for an embedding."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["distances"],
        )
        ids = response.get("ids")
        distances = response.get("distances")
        if not isinstance(ids, list) or not ids or not isinstance(distances, list) or not distances:
            return []
        first_ids = ids[0]
        first_distances = distances[0]
        if not isinstance(first_ids, list) or not isinstance(first_distances, list):
            return []

        candidates: list[ProductVectorCandidate] = []
        for product_id, distance in zip(first_ids, first_distances):
            if (
                not isinstance(product_id, str)
                or isinstance(distance, bool)
                or not isinstance(distance, (int, float))
            ):
                continue
            candidates.append(
                ProductVectorCandidate(product_id=product_id, distance=float(distance))
            )
        return candidates
