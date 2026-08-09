"""Deterministic Product documents and Chroma metadata."""

from __future__ import annotations

from typing import Any

from app.models.product import Product


def build_product_document(product: Product) -> str:
    """Build the canonical semantic representation of a Product."""
    return (
        f"Title: {product.title}\n"
        f"Category: {product.category}\n"
        f"Description: {product.description}"
    )


def build_product_metadata(product: Product) -> dict[str, Any]:
    """Build Chroma-compatible metadata from authoritative Product fields."""
    return {
        "product_id": str(product.id),
        "category": product.category,
        "price": float(product.price),
        "is_active": product.is_active,
    }
