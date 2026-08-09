"""Authentication request and response contracts."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Email/password credentials submitted to the login endpoint."""

    email: EmailStr
    password: str = Field(min_length=1)


class AccessTokenResponse(BaseModel):
    """Bearer token issued after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class UserRegistrationRequest(BaseModel):
    """Public registration payload that cannot select privileged account fields."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
