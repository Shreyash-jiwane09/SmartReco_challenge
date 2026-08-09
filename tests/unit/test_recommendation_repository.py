"""Unit tests for recommendation persistence repository behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
import app.models  # noqa: F401 -- register all mapped tables with Base metadata.
from app.models.product import Product
from app.models.user import User
from app.repositories.recommendation import RecommendationRepository
from app.schemas.recommendation import GeneratedRecommendation, RecommendedProduct


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _product(title: str) -> Product:
    return Product(
        id=uuid4(),
        title=title,
        description=f"Description for {title}",
        category="AI",
        price=Decimal("79.00"),
    )


def _generated(product_ids: list) -> GeneratedRecommendation:
    return GeneratedRecommendation(
        narrative="A tailored learning path.",
        recommendations=[
            RecommendedProduct(product_id=product_id, reason=f"Reason {index}")
            for index, product_id in enumerate(product_ids)
        ],
    )


def test_repository_creates_ordered_recommendation_and_returns_latest() -> None:
    session = _session()
    try:
        user = User(
            id=uuid4(),
            email="repository@example.com",
            hashed_password="hash",
            full_name="Repository User",
        )
        first_product = _product("First Product")
        second_product = _product("Second Product")
        session.add_all([user, first_product, second_product])
        session.commit()
        repository = RecommendationRepository(session)

        older = repository.create_for_user(
            user.id,
            _generated([first_product.id, second_product.id]),
        )
        older.created_at = REFERENCE_TIME - timedelta(minutes=1)
        session.commit()
        newer = repository.create_for_user(user.id, _generated([second_product.id]))
        newer.created_at = REFERENCE_TIME
        session.commit()

        latest = repository.get_latest_for_user(user.id)

        assert older.user_id == user.id
        assert older.narrative == "A tailored learning path."
        assert [item.product_id for item in older.products] == [first_product.id, second_product.id]
        assert [item.reason for item in older.products] == ["Reason 0", "Reason 1"]
        assert [item.position for item in older.products] == [0, 1]
        assert latest is not None
        assert latest.id == newer.id
        # SQLite does not round-trip timezone offsets; PostgreSQL coverage verifies awareness.
        assert repository.get_latest_created_at_for_user(user.id) == REFERENCE_TIME.replace(
            tzinfo=None
        )
    finally:
        session.close()
