"""Server-rendered user-platform route tests."""

from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_authentication_service,
    get_db,
    get_product_service,
    get_recommendation_service,
    get_user_service,
)
from app.core.security import decode_access_token
from app.main import app
from app.models.user import User, UserRole
from app.services.auth_service import InvalidCredentialsError
from app.services.user import DuplicateUserEmailError
from app.services.product import ProductNotFoundError
from app.services.recommendation_service import RecommendationGenerationStatus
from app.web import AUTH_COOKIE_NAME


def _user() -> User:
    return User(
        id=uuid4(),
        email="learner@example.com",
        hashed_password="unused-by-web-route-test",
        full_name="Learner",
        role=UserRole.USER,
        is_active=True,
    )


def _product(title: str = "Agentic AI Fundamentals") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        description="Build reliable agentic workflows with practical exercises.",
        category="Agentic AI",
        price=Decimal("79.00"),
        is_active=True,
    )


def _recommendation(product, narrative: str = "These picks match your recent agentic AI exploration.") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        narrative=narrative,
        created_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
        products=[SimpleNamespace(product_id=product.id, reason="Matches your recent searches.")],
    )


@pytest.fixture
def platform_client():
    user = _user()
    product = _product()
    result = Mock()
    result.scalar_one_or_none.return_value = user
    session = Mock()
    session.execute.return_value = result
    auth_service = Mock()
    auth_service.authenticate.return_value = user
    product_service = Mock()
    product_service.list_catalog_products.return_value = [product]
    product_service.search_catalog_products.return_value = [product]
    product_service.get_product.return_value = product

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_authentication_service] = lambda: auth_service
    app.dependency_overrides[get_product_service] = lambda: product_service
    try:
        with TestClient(app) as client:
            yield client, auth_service, product_service, product
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def recommendation_platform_client(platform_client):
    client, _, product_service, product = platform_client
    recommendation_service = Mock()
    recommendation_service.get_latest_for_user.return_value = None
    app.dependency_overrides[get_recommendation_service] = lambda: recommendation_service
    try:
        yield client, product_service, product, recommendation_service
    finally:
        app.dependency_overrides.pop(get_recommendation_service, None)


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={"email": "learner@example.com", "password": "correct-password"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _authenticated_user_id(client: TestClient) -> UUID:
    return UUID(decode_access_token(client.cookies[AUTH_COOKIE_NAME])["sub"])


def test_login_page_renders(platform_client) -> None:
    client, _, _, _ = platform_client

    response = client.get("/login")

    assert response.status_code == 200
    assert "Welcome to SmartReco" in response.text
    assert 'href="/signup"' in response.text


@pytest.fixture
def signup_client():
    user_service = Mock()
    app.dependency_overrides[get_user_service] = lambda: user_service
    try:
        with TestClient(app) as client:
            yield client, user_service
    finally:
        app.dependency_overrides.clear()


def test_signup_page_renders_a_regular_user_form(signup_client) -> None:
    client, _ = signup_client

    response = client.get("/signup")

    assert response.status_code == 200
    assert "Create your SmartReco account" in response.text
    assert 'name="role"' not in response.text


def test_signup_uses_public_registration_path_and_forces_user_role(signup_client) -> None:
    client, user_service = signup_client

    response = client.post(
        "/signup",
        data={
            "email": "new-user@example.com",
            "full_name": "New User",
            "password": "correct-password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?message=account-created"
    submitted = user_service.create_user.call_args.args[0]
    assert submitted.email == "new-user@example.com"
    assert submitted.role is UserRole.USER
    assert submitted.is_active is True


def test_signup_validation_and_duplicate_email_errors_are_browser_friendly(signup_client) -> None:
    client, user_service = signup_client

    invalid = client.post(
        "/signup",
        data={"email": "not-an-email", "full_name": "", "password": "short"},
    )
    user_service.create_user.side_effect = DuplicateUserEmailError("duplicate")
    duplicate = client.post(
        "/signup",
        data={
            "email": "existing@example.com",
            "full_name": "Existing User",
            "password": "correct-password",
        },
    )

    assert invalid.status_code == 422
    assert "Enter a valid email" in invalid.text
    assert duplicate.status_code == 409
    assert "account with that email already exists" in duplicate.text


def test_valid_login_sets_http_only_cookie_and_redirects(platform_client) -> None:
    client, auth_service, _, _ = platform_client

    response = client.post(
        "/login",
        data={"email": "learner@example.com", "password": "correct-password"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/products"
    assert AUTH_COOKIE_NAME in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    auth_service.authenticate.assert_called_once_with(
        email="learner@example.com", password="correct-password"
    )


def test_invalid_login_renders_generic_error(platform_client) -> None:
    client, auth_service, _, _ = platform_client
    auth_service.authenticate.side_effect = InvalidCredentialsError()

    response = client.post(
        "/login",
        data={"email": "learner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.text
    assert "wrong-password" not in response.text


def test_unauthenticated_catalog_access_redirects_to_login(platform_client) -> None:
    client, _, _, _ = platform_client

    response = client.get("/products", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_authenticated_user_can_browse_real_catalog_products(platform_client) -> None:
    client, _, product_service, product = platform_client
    _login(client)

    response = client.get("/products")

    assert response.status_code == 200
    assert product.title in response.text
    assert product.description in response.text
    product_service.list_catalog_products.assert_called_once_with()


def test_authenticated_catalog_loads_cookie_safe_tracking_and_product_click_metadata(
    platform_client,
) -> None:
    client, _, _, product = platform_client
    _login(client)

    response = client.get("/products")

    assert "static/js/tracker.js" in response.text
    assert "static/js/app.js" in response.text
    assert 'data-track-search' in response.text
    assert 'data-track-click="product_detail"' in response.text
    assert f'data-resource-id="{product.id}"' in response.text
    assert "useCookieAuth: true" in response.text
    assert "getAccessToken" not in response.text
    assert "access_token" not in response.text


def test_search_returns_matching_catalog_products(platform_client) -> None:
    client, _, product_service, product = platform_client
    _login(client)

    response = client.get("/products?query=agentic")

    assert response.status_code == 200
    assert product.title in response.text
    product_service.search_catalog_products.assert_called_once_with("agentic")


def test_empty_catalog_query_does_not_initialize_a_search_event(platform_client) -> None:
    client, _, _, _ = platform_client
    _login(client)

    response = client.get("/products")

    assert response.status_code == 200
    assert "trackingSearch" not in response.text


def test_empty_search_results_render_a_valid_empty_state(platform_client) -> None:
    client, _, product_service, _ = platform_client
    product_service.search_catalog_products.return_value = []
    _login(client)

    response = client.get("/products?query=unmatched")

    assert response.status_code == 200
    assert "No matching products" in response.text


def test_product_detail_renders_a_persisted_product(platform_client) -> None:
    client, _, product_service, product = platform_client
    _login(client)

    response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert product.title in response.text
    product_service.get_product.assert_called_once_with(product.id)


def test_product_detail_configures_product_view_and_time_spent_tracking(platform_client) -> None:
    client, _, _, product = platform_client
    _login(client)

    response = client.get(f"/products/{product.id}")

    assert response.status_code == 200
    assert f'"resourceId": "{product.id}"' in response.text
    assert response.text.count('"resourceType": "product"') == 2


def test_unknown_product_renders_not_found_page(platform_client) -> None:
    client, _, product_service, _ = platform_client
    product_service.get_product.side_effect = ProductNotFoundError("missing")
    _login(client)

    response = client.get(f"/products/{uuid4()}")

    assert response.status_code == 404
    assert "Product not found" in response.text


def test_logout_clears_browser_authentication(platform_client) -> None:
    client, _, _, _ = platform_client
    _login(client)

    response = client.post("/logout", follow_redirects=False)
    catalog_response = client.get("/products", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert AUTH_COOKIE_NAME in response.headers["set-cookie"]
    assert catalog_response.status_code == 303


def test_authenticated_user_navigates_between_catalog_and_detail(platform_client) -> None:
    client, _, _, product = platform_client
    _login(client)

    catalog_response = client.get("/products")
    detail_response = client.get(f"/products/{product.id}")

    assert catalog_response.status_code == 200
    assert detail_response.status_code == 200


def test_unauthenticated_recommendations_redirect_to_login(recommendation_platform_client) -> None:
    client, _, _, recommendation_service = recommendation_platform_client

    response = client.get("/recommendations", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    recommendation_service.get_latest_for_user.assert_not_called()


def test_recommendations_page_shows_learning_state_without_persisted_result(
    recommendation_platform_client,
) -> None:
    client, _, _, recommendation_service = recommendation_platform_client
    _login(client)

    response = client.get("/recommendations")

    assert response.status_code == 200
    assert "We are still learning your interests" in response.text
    recommendation_service.get_latest_for_user.assert_called_once_with(_authenticated_user_id(client))
    recommendation_service.generate_for_user.assert_not_called()


def test_recommendations_page_renders_persisted_narrative_products_reasons_and_links(
    recommendation_platform_client,
) -> None:
    client, product_service, product, recommendation_service = recommendation_platform_client
    recommendation_service.get_latest_for_user.return_value = _recommendation(product)
    _login(client)

    response = client.get("/recommendations")

    assert response.status_code == 200
    assert "These picks match your recent agentic AI exploration." in response.text
    assert product.title in response.text
    assert "Matches your recent searches." in response.text
    assert f'href="/products/{product.id}"' in response.text
    product_service.get_product.assert_called_once_with(product.id)
    recommendation_service.generate_for_user.assert_not_called()


def test_refresh_uses_current_user_and_preserves_latest_result_when_trigger_is_not_met(
    recommendation_platform_client,
) -> None:
    client, _, product, recommendation_service = recommendation_platform_client
    stored = _recommendation(product)
    profile = SimpleNamespace(trigger=SimpleNamespace(reason=SimpleNamespace(value="cooldown_active")))
    recommendation_service.generate_for_user.return_value = SimpleNamespace(
        status=RecommendationGenerationStatus.TRIGGER_NOT_MET,
        profile=profile,
        recommendation=None,
    )
    recommendation_service.get_latest_for_user.return_value = stored
    _login(client)

    response = client.post("/recommendations/refresh")

    assert response.status_code == 200
    assert "latest recommendations are still current" in response.text
    assert stored.narrative in response.text
    recommendation_service.generate_for_user.assert_called_once_with(_authenticated_user_id(client))


def test_refresh_renders_new_persisted_recommendation_after_success(
    recommendation_platform_client,
) -> None:
    client, _, product, recommendation_service = recommendation_platform_client
    generated = _recommendation(product, "A refreshed recommendation for your latest activity.")
    profile = SimpleNamespace(trigger=SimpleNamespace(reason=SimpleNamespace(value="search_intent")))
    recommendation_service.generate_for_user.return_value = SimpleNamespace(
        status=RecommendationGenerationStatus.GENERATED,
        profile=profile,
        recommendation=generated,
    )
    _login(client)

    response = client.post("/recommendations/refresh")

    assert response.status_code == 200
    assert generated.narrative in response.text
    assert "recommendations have been refreshed" in response.text


def test_refresh_failure_keeps_latest_persisted_recommendation_and_hides_details(
    recommendation_platform_client,
) -> None:
    client, _, product, recommendation_service = recommendation_platform_client
    stored = _recommendation(product)
    recommendation_service.generate_for_user.side_effect = RuntimeError("Mesh response: secret")
    recommendation_service.get_latest_for_user.return_value = stored
    _login(client)

    response = client.post("/recommendations/refresh")

    assert response.status_code == 200
    assert stored.narrative in response.text
    assert "We could not refresh your recommendations right now." in response.text
    assert "Mesh response: secret" not in response.text
