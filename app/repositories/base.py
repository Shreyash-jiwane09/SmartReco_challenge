"""Generic SQLAlchemy repository primitives."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Provide common persistence operations for a SQLAlchemy model."""

    def __init__(self, model: type[ModelType], session: Session) -> None:
        self.model = model
        self.session = session

    def get_by_id(self, identifier: Any) -> ModelType | None:
        """Return a model instance by primary key, if it exists."""
        statement = select(self.model).where(self.model.id == identifier)
        return self.session.execute(statement).scalar_one_or_none()

    def list(self, *, offset: int = 0, limit: int | None = None) -> list[ModelType]:
        """Return model instances ordered by their database default order."""
        statement = select(self.model).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.execute(statement).scalars().all())

    def create(self, entity: ModelType) -> ModelType:
        """Add an entity to the current transaction without committing."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(
        self,
        entity: ModelType,
        values: Mapping[str, Any],
    ) -> ModelType:
        """Apply mapped attribute updates without committing the transaction."""
        for field_name, value in values.items():
            setattr(entity, field_name, value)
        self.session.flush()
        return entity

    def delete(self, entity: ModelType) -> ModelType:
        """Mark an entity for deletion without committing the transaction."""
        self.session.delete(entity)
        self.session.flush()
        return entity
