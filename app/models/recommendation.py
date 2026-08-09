"""Recommendation persistence ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import Base


class Recommendation(Base):
    """One generated recommendation for a user at a point in time."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    products: Mapped[list["RecommendationProduct"]] = relationship(
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="RecommendationProduct.position",
    )


class RecommendationProduct(Base):
    """An ordered, explained Product selection within one Recommendation."""

    __tablename__ = "recommendation_products"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id"),
        primary_key=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[Recommendation] = relationship(back_populates="products")
    product: Mapped["Product"] = relationship()
