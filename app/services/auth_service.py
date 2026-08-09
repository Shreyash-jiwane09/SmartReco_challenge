"""Authentication application service operations."""

from __future__ import annotations

from app.core.security import verify_password
from app.models.user import User
from app.repositories.user import UserRepository


class InvalidCredentialsError(Exception):
    """Raised when login credentials cannot authenticate an active user."""


class AuthenticationService:
    """Authenticate persisted users with the project's password utilities."""

    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def authenticate(self, *, email: str, password: str) -> User:
        """Return an active user or raise one generic credential error."""
        user = self.repository.get_by_email(email)
        if (
            user is None
            or not user.is_active
            or not verify_password(password, user.hashed_password)
        ):
            raise InvalidCredentialsError("Invalid email or password")
        return user
