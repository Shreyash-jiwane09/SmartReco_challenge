"""Server-rendered presentation routes for the SmartReco user platform."""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authentication_service,
    get_current_user,
    get_product_service,
    get_recommendation_service,
    get_user_service,
)
from app.api.v1.users import create_user as register_user
from app.core.config import settings
from app.core.security import AUTH_COOKIE_NAME, create_access_token
from app.database.session import get_db
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.user import User, UserRole
from app.schemas.auth import UserRegistrationRequest
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.auth_service import AuthenticationService, InvalidCredentialsError
from app.services.user import UserService
from app.services.product import (
    ProductNotFoundError,
    ProductService,
    ProductServiceError,
)
from app.services.recommendation_service import (
    RecommendationGenerationStatus,
    RecommendationService,
)


templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter(include_in_schema=False)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecommendationProductDisplay:
    """A persisted recommendation selection paired with its current catalog product."""

    product: Product
    reason: str


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
    return {
        "request": request,
        "current_user": user,
        "tracking_product_view": None,
        "tracking_time_spent": None,
        **values,
    }


def _recommendation_products(
    recommendation: Recommendation, service: ProductService
) -> list[RecommendationProductDisplay]:
    """Resolve persisted product IDs through the authoritative product service."""
    products: list[RecommendationProductDisplay] = []
    for selection in recommendation.products:
        try:
            product = service.get_product(selection.product_id)
        except ProductNotFoundError:
            logger.warning(
                "Skipping missing product from persisted recommendation",
                extra={"product_id": str(selection.product_id)},
            )
            continue
        products.append(RecommendationProductDisplay(product=product, reason=selection.reason))
    return products


def _recommendation_message(
    status: RecommendationGenerationStatus, trigger_reason: object
) -> str:
    """Translate normal frozen-service outcomes into concise browser copy."""
    if status is RecommendationGenerationStatus.TRIGGER_NOT_MET:
        if getattr(trigger_reason, "value", trigger_reason) == "cooldown_active":
            return "Your latest recommendations are still current. Browse a little longer before refreshing."
        return "Keep exploring products so SmartReco can learn your interests."
    if status is RecommendationGenerationStatus.NO_PRODUCTS:
        return "We could not find matching catalog products yet. Keep exploring and try again soon."
    return "Your recommendations have been refreshed."


def _admin_access_response(request: Request, user: User | None) -> Response | None:
    """Return the appropriate browser response unless the user is an admin."""
    if user is None:
        return _redirect_to_login()
    if user.role is not UserRole.ADMIN:
        return templates.TemplateResponse(
            request,
            "admin/forbidden.html",
            _context(request, user),
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return None


def _product_form_data(
    title: str,
    description: str,
    category: str,
    price: str,
    is_active: bool,
) -> tuple[ProductCreate | None, dict[str, object] | None]:
    """Coerce a browser form into the established product creation contract."""
    values = {
        "title": title.strip(),
        "description": description.strip(),
        "category": category.strip(),
        "price": price.strip(),
        "is_active": is_active,
    }
    if not all((values["title"], values["description"], values["category"])):
        return None, values
    try:
        return ProductCreate.model_validate(values), None
    except ValidationError:
        return None, values


def _product_form_response(
    request: Request,
    user: User,
    *,
    product: Product | None = None,
    values: dict[str, object] | None = None,
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    """Render the shared create/edit form with safe browser-facing feedback."""
    return templates.TemplateResponse(
        request,
        "admin/products/form.html",
        _context(
            request,
            user,
            product=product,
            values=values or {},
            is_active=(product.is_active if product is not None else True),
            error=error,
        ),
        status_code=status_code,
    )


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
    message: str | None = None,
    user: User | None = Depends(get_web_current_user),
) -> Response:
    """Render the login form or skip it for an existing authenticated session."""
    if user is not None:
        return RedirectResponse("/products", status_code=status.HTTP_303_SEE_OTHER)
    messages = {"account-created": "Your account has been created. Please sign in."}
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        _context(request, user, message=messages.get(message)),
    )


@router.get("/signup", name="signup_page")
def signup_page(
    request: Request,
    user: User | None = Depends(get_web_current_user),
) -> Response:
    """Render the public registration form for a regular SmartReco account."""
    if user is not None:
        return RedirectResponse("/products", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "auth/signup.html", _context(request, user))


@router.post("/signup", name="signup_submit")
def signup_submit(
    request: Request,
    email: str = Form(""),
    full_name: str = Form(""),
    password: str = Form(""),
    service: UserService = Depends(get_user_service),
) -> Response:
    """Register through the established public registration endpoint contract."""
    values = {"email": email, "full_name": full_name}
    try:
        register_user(
            UserRegistrationRequest(
                email=email.strip(),
                full_name=full_name.strip(),
                password=password,
            ),
            service,
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            _context(
                request,
                None,
                error="Enter a valid email, name, and password of at least 8 characters.",
                **values,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            error = "An account with that email already exists. Please sign in instead."
        else:
            logger.exception("Public registration failed")
            error = "We could not create your account right now. Please try again."
        return templates.TemplateResponse(
            request,
            "auth/signup.html",
            _context(request, None, error=error, **values),
            status_code=exc.status_code,
        )
    return RedirectResponse("/login?message=account-created", status_code=status.HTTP_303_SEE_OTHER)


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
        _context(
            request,
            user,
            product=product,
            tracking_product_view={
                "resourceType": "product",
                "resourceId": str(product.id),
            },
            tracking_time_spent={
                "resourceType": "product",
                "resourceId": str(product.id),
            },
        ),
    )


@router.get("/recommendations", name="recommendations_page")
def recommendations_page(
    request: Request,
    user: User | None = Depends(get_web_current_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    """Render the authenticated user's latest persisted recommendation without generating."""
    if user is None:
        return _redirect_to_login()
    recommendation = recommendation_service.get_latest_for_user(user.id)
    products = (
        _recommendation_products(recommendation, product_service)
        if recommendation is not None
        else []
    )
    return templates.TemplateResponse(
        request,
        "recommendations/index.html",
        _context(
            request,
            user,
            recommendation=recommendation,
            products=products,
            message=None,
            error=None,
        ),
    )


@router.post("/recommendations/refresh", name="recommendations_refresh")
def recommendations_refresh(
    request: Request,
    user: User | None = Depends(get_web_current_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    product_service: ProductService = Depends(get_product_service),
) -> Response:
    """Ask the frozen service to refresh, then preserve and display persisted state."""
    if user is None:
        return _redirect_to_login()
    try:
        result = recommendation_service.generate_for_user(user.id)
        recommendation = result.recommendation or recommendation_service.get_latest_for_user(user.id)
        message = _recommendation_message(result.status, result.profile.trigger.reason)
        error = None
    except Exception:
        logger.exception("Recommendation refresh failed", extra={"user_id": str(user.id)})
        recommendation = recommendation_service.get_latest_for_user(user.id)
        message = None
        error = "We could not refresh your recommendations right now. Please try again shortly."

    products = (
        _recommendation_products(recommendation, product_service)
        if recommendation is not None
        else []
    )
    return templates.TemplateResponse(
        request,
        "recommendations/index.html",
        _context(
            request,
            user,
            recommendation=recommendation,
            products=products,
            message=message,
            error=error,
        ),
    )


@router.get("/admin", name="admin_dashboard")
def admin_dashboard(
    request: Request,
    user: User | None = Depends(get_web_current_user),
) -> Response:
    """Provide a stable entry point for the minimal product-management UI."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    return RedirectResponse("/admin/products", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/admin/products", name="admin_products")
def admin_products(
    request: Request,
    message: str | None = None,
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Render every persisted product for an authorized administrator."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    assert user is not None
    messages = {
        "created": "Product created and indexed.",
        "updated": "Product updated and re-indexed.",
        "deleted": "Product deleted from the catalog and index.",
    }
    return templates.TemplateResponse(
        request,
        "admin/products/list.html",
        _context(
            request,
            user,
            products=service.list_products(),
            message=messages.get(message),
        ),
    )


@router.get("/admin/products/new", name="admin_product_create_form")
def admin_product_create_form(
    request: Request,
    user: User | None = Depends(get_web_current_user),
) -> Response:
    """Render the admin-only product creation form."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    assert user is not None
    return _product_form_response(request, user)


@router.post("/admin/products", name="admin_product_create")
def admin_product_create(
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    is_active: str | None = Form(None),
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Create a product through the established SQL and Chroma service path."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    assert user is not None
    payload, values = _product_form_data(title, description, category, price, is_active == "on")
    if payload is None:
        return _product_form_response(
            request,
            user,
            values=values,
            error="Enter a title, description, category, and valid price.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        service.create_product(payload)
    except ProductServiceError:
        logger.exception("Admin product creation failed")
        return _product_form_response(
            request,
            user,
            values=values,
            error="We could not create this product right now. Please try again.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RedirectResponse("/admin/products?message=created", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/admin/products/{product_id}/edit", name="admin_product_edit_form")
def admin_product_edit_form(
    request: Request,
    product_id: uuid.UUID,
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Render a pre-populated edit form for one persisted product."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    assert user is not None
    try:
        product = service.get_product(product_id)
    except ProductNotFoundError:
        return templates.TemplateResponse(
            request,
            "products/not_found.html",
            _context(request, user),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return _product_form_response(request, user, product=product)


@router.post("/admin/products/{product_id}", name="admin_product_update")
def admin_product_update(
    request: Request,
    product_id: uuid.UUID,
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(""),
    price: str = Form(""),
    is_active: str | None = Form(None),
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Update a product through the established SQL and Chroma service path."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    assert user is not None
    payload, values = _product_form_data(title, description, category, price, is_active == "on")
    if payload is None:
        return _product_form_response(
            request,
            user,
            values=values,
            error="Enter a title, description, category, and valid price.",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    try:
        service.update_product(product_id, ProductUpdate.model_validate(payload.model_dump()))
    except ProductNotFoundError:
        return templates.TemplateResponse(
            request,
            "products/not_found.html",
            _context(request, user),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except ProductServiceError:
        logger.exception("Admin product update failed", extra={"product_id": str(product_id)})
        return _product_form_response(
            request,
            user,
            values=values,
            error="We could not update this product right now. Please try again.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RedirectResponse("/admin/products?message=updated", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/products/{product_id}/delete", name="admin_product_delete")
def admin_product_delete(
    request: Request,
    product_id: uuid.UUID,
    user: User | None = Depends(get_web_current_user),
    service: ProductService = Depends(get_product_service),
) -> Response:
    """Delete one product through the established SQL and Chroma service path."""
    access_response = _admin_access_response(request, user)
    if access_response is not None:
        return access_response
    try:
        service.delete_product(product_id)
    except ProductNotFoundError:
        return templates.TemplateResponse(
            request,
            "products/not_found.html",
            _context(request, user),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except ProductServiceError:
        logger.exception("Admin product deletion failed", extra={"product_id": str(product_id)})
        return templates.TemplateResponse(
            request,
            "admin/products/list.html",
            _context(
                request,
                user,
                products=service.list_products(),
                error="We could not delete this product right now. Please try again.",
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return RedirectResponse("/admin/products?message=deleted", status_code=status.HTTP_303_SEE_OTHER)
