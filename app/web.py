"""Server-rendered presentation routes for the SmartReco user platform."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authentication_service,
    get_current_user,
    get_product_service,
)
from app.core.config import settings
from app.core.security import create_access_token
from app.database.session import get_db
from app.models.user import User
from app.services.auth_service import AuthenticationService, InvalidCredentialsError
from app.services.product import ProductNotFoundError, ProductService


AUTH_COOKIE_NAME = "smartreco_access_token"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter(include_in_schema=False)


def get_web_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the existing JWT format from the browser cookie when present."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    try:
        return get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db
        )
    except Exception:
        return None


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


def _context(request: Request, user: User | None, **values: object) -> dict[str, object]:
    return {"request": request, "current_user": user, **values}


@router.get("/", name="home")
def home(user: User | None = Depends(get_web_current_user)) -> RedirectResponse:
    """Send visitors to their authenticated catalog or the login page."""
    return RedirectResponse(
        "/products" if user is not None else "/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/login", name="login_page")
def login_page(
    request: Request,
    user: User | None = Depends(get_web_current_user),
) -> Response:
    """Render the login form or skip it for an existing authenticated session."""
    if user is not None:
        return RedirectResponse("/products", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "auth/login.html", _context(request, user))


@router.post("/login", name="login_submit")
def login_submit(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    service: AuthenticationService = Depends(get_authentication_service),
) -> Response:
    """Authenticate with the canonical service and persist its JWT in a cookie."""
    try:
        user = service.authenticate(email=email, password=password)
    except InvalidCredentialsError:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            _context(request, None, error="Invalid email or password", email=email),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse("/products", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_access_token(str(user.id)),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/",
    )
    return response


@router.post("/logout", name="logout")
def logout() -> RedirectResponse:
    """Clear the browser JWT cookie without introducing a token blacklist."""
    response = RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


@router.get("/products", name="catalog")
def catalog(
    request: Request,
    query: str = "",
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Render active catalog products and optional read-only search results."""
    if user is None:
        return _redirect_to_login()
    normalized_query = query.strip()
    products = (
        service.search_catalog_products(normalized_query)
        if normalized_query
        else service.list_catalog_products()
    )
    return templates.TemplateResponse(
        request,
        "products/list.html",
        _context(request, user, products=products, query=normalized_query),
    )


@router.get("/products/{product_id}", name="product_detail")
def product_detail(
    request: Request,
    product_id: uuid.UUID,
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Render one real catalog product or a browser-friendly not-found page."""
    if user is None:
        return _redirect_to_login()
    try:
        product = service.get_product(product_id)
    except ProductNotFoundError:
        return templates.TemplateResponse(
            request,
            "products/not_found.html",
            _context(request, user),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return templates.TemplateResponse(
        request,
        "products/detail.html",
        _context(request, user, product=product),
    )
