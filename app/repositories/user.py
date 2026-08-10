"""Repository operations for users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Provide persistence operations for users."""

    def __init__(self, session: Session) -> None:
        super().__init__(User, session)

    def get_by_email(self, email: str) -> User | None:
        """Return a user by email address, if it exists."""
        statement = select(User).where(User.email == email)
        return self.session.execute(statement).scalar_one_or_none()

    def list_active_recommendation_recipients(self) -> list[User]:
        """Return active standard-user accounts eligible for scheduled processing."""
        statement = (
            select(User)
            .where(User.role == UserRole.USER, User.is_active.is_(True))
            .order_by(User.created_at.asc(), User.id.asc())
        )
        return list(self.session.execute(statement).scalars().all())
