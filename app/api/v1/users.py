"""User CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_user_service, require_admin
from app.models.user import User, UserRole
from app.schemas.auth import UserRegistrationRequest
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user import (
    DuplicateUserEmailError,
    UserNotFoundError,
    UserService,
)


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    """Return all users."""
    return service.list_users()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Return a user by identifier."""
    try:
        return service.get_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserRegistrationRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Register a regular user without accepting client-controlled roles."""
    try:
        return service.create_user(
            UserCreate(
                email=payload.email,
                full_name=payload.full_name,
                password=payload.password,
                role=UserRole.USER,
                is_active=True,
            )
        )
    except DuplicateUserEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Update a user."""
    try:
        return service.update_user(user_id, payload)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateUserEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_user(
    user_id: uuid.UUID,
    _: User = Depends(require_admin),
    service: UserService = Depends(get_user_service),
) -> Response:
    """Delete a user."""
    try:
        service.delete_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
