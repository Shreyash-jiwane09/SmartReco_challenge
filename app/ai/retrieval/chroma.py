"""Persistent Chroma storage for Product vectors."""

from __future__ import annotations

from typing import Any

import chromadb


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
