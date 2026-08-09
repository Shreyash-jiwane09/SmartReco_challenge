"""Semantic Product retrieval grounded in the authoritative SQL catalog."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.ai.retrieval.chroma import ProductChromaStore
from app.ai.retrieval.embeddings import MeshEmbeddingService
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.repositories.product import ProductRepository
from app.schemas.behavior import BehavioralProfile


DEFAULT_TOP_K = 5
ACTIVE_PRODUCT_FILTER = {"is_active": True}


@dataclass(frozen=True)
class RetrievedProduct:
    """An SQL-authoritative Product ranked by its Chroma retrieval distance."""

    product_id: UUID
    title: str
    description: str
    category: str
    price: Decimal
    distance: float


class SemanticProductRetrievalService:
    """Resolve semantic candidates into active, authoritative catalog products."""

    def __init__(
        self,
        *,
        query_builder: BehavioralProfileQueryBuilder,
        embedding_service: MeshEmbeddingService,
        store: ProductChromaStore,
        product_repository: ProductRepository,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        self.query_builder = query_builder
        self.embedding_service = embedding_service
        self.store = store
        self.product_repository = product_repository
        self.top_k = top_k

    def retrieve(
        self,
        profile: BehavioralProfile,
        *,
        top_k: int | None = None,
    ) -> list[RetrievedProduct]:
        """Retrieve active SQL Products in Chroma's semantic ranking order."""
        requested_top_k = self.top_k if top_k is None else top_k
        if requested_top_k < 1:
            raise ValueError("top_k must be at least 1")

        query = self.query_builder.build(profile)
        if not query.sufficient_signal:
            return []

        candidates = self.store.query_products(
            query_embedding=self.embedding_service.embed(query.text),
            top_k=requested_top_k,
            where=ACTIVE_PRODUCT_FILTER,
        )
        retrieved_products: list[RetrievedProduct] = []
        seen_product_ids: set[str] = set()
        for candidate in candidates:
            if candidate.product_id in seen_product_ids:
                continue
            seen_product_ids.add(candidate.product_id)
            try:
                product_id = UUID(candidate.product_id)
            except ValueError:
                continue
            product = self.product_repository.get_by_id(product_id)
            if product is None or not product.is_active:
                continue
            retrieved_products.append(
                RetrievedProduct(
                    product_id=product.id,
                    title=product.title,
                    description=product.description,
                    category=product.category,
                    price=product.price,
                    distance=candidate.distance,
                )
            )
        return retrieved_products
