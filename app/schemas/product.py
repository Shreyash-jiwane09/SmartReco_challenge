"""Pydantic schemas for product API payloads."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductBase(BaseModel):
    """Common product fields."""

    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    category: str
    price: Decimal
    is_active: bool = True


class ProductCreate(ProductBase):
    """Payload for creating a product."""


class ProductUpdate(BaseModel):
    """Payload for partially updating a product."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    description: str | None = None
    category: str | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class ProductResponse(ProductBase):
    """Public product response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
