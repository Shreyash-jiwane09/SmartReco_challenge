"""Focused API authentication and role authorization tests."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user, require_admin
from app.api.router import api_router
from app.api.v1.auth import login, router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.users import create_user
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, UserRegistrationRequest
from app.services.auth_service import AuthenticationService, InvalidCredentialsError


def _user(role: UserRole = UserRole.USER) -> User:
    return User(
        id=uuid4(),
        email="account@example.com",
        hashed_password=hash_password("correct-password"),
        full_name="Account",
        role=role,
        is_active=True,
    )


def _service_with(user: User | None) -> AuthenticationService:
    repository = Mock()
    repository.get_by_email.return_value = user
    return AuthenticationService(repository)


def test_valid_email_password_login_returns_a_usable_token() -> None:
    user = _user()

    response = login(
        LoginRequest(email=user.email, password="correct-password"),
        _service_with(user),
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=response.access_token
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    session = Mock()
    session.execute.return_value = result
    resolved = get_current_user(credentials, session)

    assert response.token_type == "bearer"
    assert resolved is user


@pytest.mark.parametrize("user,password", [(_user(), "wrong-password"), (None, "any-password")])
def test_login_rejects_wrong_password_or_unknown_email(
    user: User | None,
    password: str,
) -> None:
    with pytest.raises(InvalidCredentialsError, match="Invalid email or password"):
        _service_with(user).authenticate(email="account@example.com", password=password)


def test_login_endpoint_returns_generic_invalid_credentials_error() -> None:
    with pytest.raises(HTTPException) as exc_info:
        login(
            LoginRequest(email="missing@example.com", password="wrong-password"),
            _service_with(None),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"


@pytest.mark.parametrize("credentials", [None, HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")])
def test_current_user_rejects_missing_or_malformed_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, Mock())

    assert exc_info.value.status_code == 401


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_regular_user_is_rejected_from_each_product_mutation(operation: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_admin(_user(UserRole.USER))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin access required"
    assert operation in {"create", "update", "delete"}


def test_admin_is_authorized_for_product_mutations() -> None:
    admin = _user(UserRole.ADMIN)

    assert require_admin(admin) is admin
    protected_routes = [
        route
        for route in products_router.routes
        if "POST" in route.methods or "PATCH" in route.methods or "DELETE" in route.methods
    ]
    assert len(protected_routes) == 3
    assert all(
        any(dependency.call is require_admin for dependency in route.dependant.dependencies)
        for route in protected_routes
    )


def test_public_registration_forces_the_regular_user_role() -> None:
    created_user = _user(UserRole.USER)
    service = Mock()
    service.create_user.return_value = created_user

    response = create_user(
        UserRegistrationRequest.model_validate(
            {
                "email": "new-user@example.com",
                "full_name": "New User",
                "password": "correct-password",
                "role": "ADMIN",
            }
        ),
        service,
    )

    submitted = service.create_user.call_args.args[0]
    assert response is created_user
    assert submitted.role is UserRole.USER
    assert submitted.is_active is True


def test_public_registration_api_contract_does_not_offer_role_selection() -> None:
    assert set(UserRegistrationRequest.model_fields) == {"email", "full_name", "password"}


def test_auth_router_is_registered() -> None:
    assert auth_router.prefix == "/auth"
    assert [route.path for route in auth_router.routes] == ["/auth/login"]
    assert any(getattr(route, "original_router", None) is auth_router for route in api_router.routes)
