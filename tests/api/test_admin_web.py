"""Browser coverage for the minimum admin product-management interface."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_authentication_service, get_db, get_product_service
from app.main import app
from app.models.user import User, UserRole
from app.services.product import ProductNotFoundError


def _user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        email=f"{role.value.lower()}@example.com",
        hashed_password="unused",
        full_name=role.value.title(),
        role=role,
        is_active=True,
    )


def _product() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        title="Agentic AI Fundamentals",
        description="Build reliable agent workflows.",
        category="Agentic AI",
        price=Decimal("79.00"),
        is_active=True,
    )


@pytest.fixture
def admin_client():
    user = _user(UserRole.ADMIN)
    product = _product()
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = user
    auth_service = Mock()
    auth_service.authenticate.return_value = user
    product_service = Mock()
    product_service.list_catalog_products.return_value = []
    product_service.list_products.return_value = [product]
    product_service.get_product.return_value = product

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_authentication_service] = lambda: auth_service
    app.dependency_overrides[get_product_service] = lambda: product_service
    try:
        with TestClient(app) as client:
            yield client, user, product, product_service
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def user_client():
    user = _user(UserRole.USER)
    session = Mock()
    session.execute.return_value.scalar_one_or_none.return_value = user
    auth_service = Mock()
    auth_service.authenticate.return_value = user
    product_service = Mock()
    product_service.list_catalog_products.return_value = []

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_authentication_service] = lambda: auth_service
    app.dependency_overrides[get_product_service] = lambda: product_service
    try:
        with TestClient(app) as client:
            yield client, product_service
    finally:
        app.dependency_overrides.clear()


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/login", data={"email": email, "password": "correct-password"}, follow_redirects=False
    )
    assert response.status_code == 303


def _form_data() -> dict[str, str]:
    return {
        "title": "Practical LangGraph",
        "description": "Build stateful graph applications.",
        "category": "Agentic AI",
        "price": "129.00",
        "is_active": "on",
    }


def test_unauthenticated_user_is_redirected_from_admin(admin_client) -> None:
    client, _, _, product_service = admin_client

    response = client.get("/admin/products", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    product_service.list_products.assert_not_called()


def test_regular_user_is_denied_admin_access_and_navigation(user_client) -> None:
    client, product_service = user_client
    _login(client, "user@example.com")

    response = client.get("/admin/products")
    catalog = client.get("/products")

    assert response.status_code == 403
    assert "Admin access required" in response.text
    assert "Admin" not in catalog.text
    product_service.list_products.assert_not_called()


def test_admin_can_view_real_products_and_admin_navigation(admin_client) -> None:
    client, _, product, product_service = admin_client
    _login(client, "admin@example.com")

    response = client.get("/admin/products")

    assert response.status_code == 200
    assert product.title in response.text
    assert product.category in response.text
    assert "Admin" in response.text
    product_service.list_products.assert_called_once_with()


def test_admin_create_form_and_validation(admin_client) -> None:
    client, _, _, product_service = admin_client
    _login(client, "admin@example.com")

    form = client.get("/admin/products/new")
    invalid = client.post("/admin/products", data={"title": "", "price": "not-a-price"})

    assert form.status_code == 200
    assert "Create product" in form.text
    assert invalid.status_code == 422
    assert "Enter a title, description, category, and valid price." in invalid.text
    product_service.create_product.assert_not_called()


def test_admin_create_calls_product_service_and_redirects(admin_client) -> None:
    client, _, _, product_service = admin_client
    _login(client, "admin@example.com")

    response = client.post("/admin/products", data=_form_data(), follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/products?message=created"
    payload = product_service.create_product.call_args.args[0]
    assert payload.title == "Practical LangGraph"
    assert payload.price == Decimal("129.00")


def test_regular_user_cannot_mutate_products_through_admin_routes(user_client) -> None:
    client, product_service = user_client
    _login(client, "user@example.com")
    product_id = uuid4()

    create = client.post("/admin/products", data=_form_data())
    update = client.post(f"/admin/products/{product_id}", data=_form_data())
    delete = client.post(f"/admin/products/{product_id}/delete")

    assert [create.status_code, update.status_code, delete.status_code] == [403, 403, 403]
    product_service.create_product.assert_not_called()
    product_service.update_product.assert_not_called()
    product_service.delete_product.assert_not_called()


def test_admin_edit_prepopulates_and_update_uses_product_service(admin_client) -> None:
    client, _, product, product_service = admin_client
    _login(client, "admin@example.com")

    form = client.get(f"/admin/products/{product.id}/edit")
    update = client.post(f"/admin/products/{product.id}", data=_form_data(), follow_redirects=False)

    assert form.status_code == 200
    assert product.title in form.text
    assert update.status_code == 303
    assert update.headers["location"] == "/admin/products?message=updated"
    product_service.update_product.assert_called_once()
    assert product_service.update_product.call_args.args[0] == product.id


def test_unknown_admin_edit_renders_not_found(admin_client) -> None:
    client, _, _, product_service = admin_client
    product_service.get_product.side_effect = ProductNotFoundError("missing")
    _login(client, "admin@example.com")

    response = client.get(f"/admin/products/{uuid4()}/edit")

    assert response.status_code == 404
    assert "Product not found" in response.text


def test_admin_delete_is_post_only_and_uses_product_service(admin_client) -> None:
    client, _, product, product_service = admin_client
    _login(client, "admin@example.com")

    get_response = client.get(f"/admin/products/{product.id}/delete")
    delete = client.post(f"/admin/products/{product.id}/delete", follow_redirects=False)

    assert get_response.status_code == 405
    assert delete.status_code == 303
    assert delete.headers["location"] == "/admin/products?message=deleted"
    product_service.delete_product.assert_called_once_with(product.id)
