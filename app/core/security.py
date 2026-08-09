"""Password hashing and JWT security utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.core.config import settings



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
AUTH_COOKIE_NAME = "smartreco_access_token"


def hash_password(password: str) -> str:
    """Return a bcrypt hash for a plaintext password."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return pwd_context.verify(password, hashed_password)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(subject: str) -> str:
    """Create a signed access token for the supplied subject."""
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    claims = {
        "sub": subject,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(
        claims,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access token, raising JWTError when invalid."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        subject = payload["sub"]
        issued_at = payload["iat"]
        expires_at = payload["exp"]
        if (
            not isinstance(subject, str)
            or not isinstance(issued_at, int)
            or not isinstance(expires_at, int)
        ):
            raise JWTError("Invalid access token claims")
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise JWTError("Invalid access token") from exc

    return {
        "sub": subject,
        "iat": issued_at,
        "exp": expires_at,
    }
