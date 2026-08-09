"""PostgreSQL integration tests for recommendation persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.user import User
from app.repositories.product import ProductRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.user import UserRepository
from app.schemas.recommendation import GeneratedRecommendation, RecommendedProduct


REFERENCE_TIME = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _product(title: str) -> Product:
    return Product(
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


def test_persisted_recommendations_preserve_catalog_associations_and_latest_timestamp(
    db_session: Session,
) -> None:
    user = UserRepository(db_session).create(
        User(
            email="recommendations@example.com",
            hashed_password="hash",
            full_name="Recommendation User",
        )
    )
    product_repository = ProductRepository(db_session)
    first_product = product_repository.create(_product("First Product"))
    second_product = product_repository.create(_product("Second Product"))
    db_session.commit()
    repository = RecommendationRepository(db_session)

    older = repository.create_for_user(
        user.id,
        _generated([first_product.id, second_product.id]),
    )
    older.created_at = REFERENCE_TIME - timedelta(minutes=1)
    db_session.commit()
    newer = repository.create_for_user(user.id, _generated([second_product.id]))
    newer.created_at = REFERENCE_TIME
    db_session.commit()

    latest = repository.get_latest_for_user(user.id)

    assert older.id is not None
    assert older.user_id == user.id
    assert older.narrative == "A tailored learning path."
    assert [item.product_id for item in older.products] == [first_product.id, second_product.id]
    assert [item.product.id for item in older.products] == [first_product.id, second_product.id]
    assert [item.reason for item in older.products] == ["Reason 0", "Reason 1"]
    assert [item.position for item in older.products] == [0, 1]
    assert older.created_at.tzinfo is not None
    assert latest is not None
    assert latest.id == newer.id
    assert repository.get_latest_created_at_for_user(user.id) == REFERENCE_TIME


def test_recommendation_with_nonexistent_product_fails_database_integrity(
    db_session: Session,
) -> None:
    user = UserRepository(db_session).create(
        User(
            email="recommendation-fk@example.com",
            hashed_password="hash",
            full_name="Recommendation Foreign Key User",
        )
    )
    db_session.commit()
    repository = RecommendationRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.create_for_user(user.id, _generated([uuid4()]))

    db_session.rollback()
