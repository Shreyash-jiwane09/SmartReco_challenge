"""Product vector indexing coordination."""

from __future__ import annotations

import uuid

from app.ai.retrieval.chroma import ProductChromaStore
from app.ai.retrieval.embeddings import MeshEmbeddingService
from app.ai.retrieval.product_document import (
    build_product_document,
    build_product_metadata,
)
from app.core.config import settings
from app.models.product import Product


class ProductVectorService:
    """Coordinate deterministic Product indexing without Product CRUD coupling."""

    def __init__(
        self,
        embedding_service: MeshEmbeddingService,
        store: ProductChromaStore,
    ) -> None:
        self.embedding_service = embedding_service
        self.store = store

    @classmethod
    def from_settings(cls) -> "ProductVectorService":
        """Construct the service from application configuration."""
        return cls(
            embedding_service=MeshEmbeddingService(
                api_key=settings.mesh_api_key,
                model=settings.mesh_embedding_model,
            ),
            store=ProductChromaStore(
                persist_directory=settings.chroma_persist_directory,
                collection_name=settings.chroma_collection_name,
            ),
        )

    def upsert_product(self, product: Product) -> str:
        """Embed and upsert a Product under its SQL UUID."""
        document = build_product_document(product)
        product_id = str(product.id)
        return self.store.upsert_product(
            product_id=product_id,
            document=document,
            metadata=build_product_metadata(product),
            embedding=self.embedding_service.embed(document),
        )

    def delete_product(self, product_id: uuid.UUID | str) -> None:
        """Delete an indexed Product without touching PostgreSQL."""
        self.store.delete_product(str(product_id))
