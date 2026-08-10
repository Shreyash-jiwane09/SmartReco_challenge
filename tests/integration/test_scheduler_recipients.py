"""Database-backed recipient selection tests for scheduled processing."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.repositories.user import UserRepository


def _user(email: str, *, role: UserRole = UserRole.USER, is_active: bool = True) -> User:
    return User(
        email=email,
        hashed_password="hash",
        full_name=email,
        role=role,
        is_active=is_active,
    )


def test_list_active_recommendation_recipients_excludes_admins_and_inactive_users(
    db_session: Session,
) -> None:
    repository = UserRepository(db_session)
    recipient = repository.create(_user("recipient@example.com"))
    repository.create(_user("admin@example.com", role=UserRole.ADMIN))
    repository.create(_user("inactive@example.com", is_active=False))
    db_session.commit()

    recipients = repository.list_active_recommendation_recipients()

    assert [user.id for user in recipients] == [recipient.id]
