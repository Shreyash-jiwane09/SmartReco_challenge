"""Email/password authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_authentication_service
from app.core.security import create_access_token
from app.schemas.auth import AccessTokenResponse, LoginRequest
from app.services.auth_service import AuthenticationService, InvalidCredentialsError


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    service: AuthenticationService = Depends(get_authentication_service),
) -> AccessTokenResponse:
    """Authenticate an active user and issue the project's bearer JWT."""
    try:
        user = service.authenticate(email=str(payload.email), password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return AccessTokenResponse(access_token=create_access_token(str(user.id)))
