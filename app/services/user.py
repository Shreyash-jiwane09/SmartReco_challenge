"""User service operations and domain rules."""

from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserServiceError(Exception):
    """Base exception for user service failures."""


class UserNotFoundError(UserServiceError):
    """Raised when a requested user does not exist."""


class DuplicateUserEmailError(UserServiceError):
    """Raised when an email address is already assigned to another user."""


class UserService:
    """Coordinate user persistence and user-related business rules."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def get_user(self, user_id: uuid.UUID) -> User:
        """Return a user by identifier or raise a domain exception."""
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} was not found")
        return user

    def list_users(self, *, offset: int = 0, limit: int | None = None) -> list[User]:
        """Return users from the repository."""
        return self.repository.list(offset=offset, limit=limit)

    def create_user(self, data: UserCreate) -> User:
        """Create and persist a user with a hashed password."""
        if self.repository.get_by_email(str(data.email)) is not None:
            raise DuplicateUserEmailError(
                f"A user with email {data.email} already exists"
            )

        user = User(
            email=str(data.email),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=data.role,
            is_active=data.is_active,
        )
        self.repository.create(user)
        self.repository.session.commit()
        self.repository.session.refresh(user)
        return user

    def update_user(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        """Update a user and hash a replacement password when supplied."""
        user = self.get_user(user_id)
        values = data.model_dump(exclude_unset=True)

        email = values.get("email")
        if email is not None:
            email = str(email)
            existing_user = self.repository.get_by_email(email)
            if existing_user is not None and existing_user.id != user.id:
                raise DuplicateUserEmailError(
                    f"A user with email {email} already exists"
                )
            values["email"] = email

        password = values.pop("password", None)
        if password is not None:
            values["hashed_password"] = hash_password(password)

        self.repository.update(user, values)
        self.repository.session.commit()
        self.repository.session.refresh(user)
        return user

    def delete_user(self, user_id: uuid.UUID) -> User:
        """Delete a user and commit the transaction."""
        user = self.get_user(user_id)
        self.repository.delete(user)
        self.repository.session.commit()
        return user
