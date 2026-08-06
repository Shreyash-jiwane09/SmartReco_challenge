"""Pydantic schemas for user API payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserBase(BaseModel):
    """Common user fields."""

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    full_name: str
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserCreate(UserBase):
    """Payload for creating a user."""

    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    """Payload for partially updating a user."""

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    """Public user response."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
