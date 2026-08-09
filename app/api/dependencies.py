"""Shared FastAPI dependency exports."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import AUTH_COOKIE_NAME, decode_access_token
from app.database.session import get_db
from app.ai.agent.graph import build_recommendation_graph
from app.ai.mesh.client import MeshRecommendationClient
from app.ai.retrieval.query_builder import BehavioralProfileQueryBuilder
from app.ai.retrieval.retriever import SemanticProductRetrievalService
from app.core.config import settings
from app.models.user import User, UserRole
from app.repositories.event import EventRepository
from app.repositories.product import ProductRepository
from app.repositories.recommendation import RecommendationRepository
from app.repositories.user import UserRepository
from app.services.behavior import BehaviorProfileService
from app.services.auth_service import AuthenticationService
from app.services.event_service import EventService
from app.services.product import ProductService
from app.services.recommendation_service import RecommendationService
from app.services.user import UserService
from app.services.vector_service import ProductVectorService


bearer_scheme = HTTPBearer(auto_error=False)


def get_authentication_service(
    db: Session = Depends(get_db),
) -> AuthenticationService:
    """Build authentication dependencies for the current request."""
    return AuthenticationService(UserRepository(db))


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Build a user service for the current request transaction."""
    return UserService(UserRepository(db))


def get_product_vector_service() -> ProductVectorService:
    """Build Product vector indexing dependencies from configuration."""
    return ProductVectorService.from_settings()


def get_product_service(
    db: Session = Depends(get_db),
    vector_service: ProductVectorService = Depends(get_product_vector_service),
) -> ProductService:
    """Build a product service for the current request transaction."""
    return ProductService(ProductRepository(db), vector_service)


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    """Build an event service for the current request transaction."""
    return EventService(EventRepository(db))


def get_recommendation_service(
    db: Session = Depends(get_db),
    vector_service: ProductVectorService = Depends(get_product_vector_service),
) -> RecommendationService:
    """Build the complete recommendation pipeline for the current request."""
    product_repository = ProductRepository(db)
    behavior_profile_service = BehaviorProfileService(
        EventRepository(db),
        product_repository,
    )
    semantic_retrieval_service = SemanticProductRetrievalService(
        query_builder=BehavioralProfileQueryBuilder(),
        embedding_service=vector_service.embedding_service,
        store=vector_service.store,
        product_repository=product_repository,
    )
    recommendation_client = MeshRecommendationClient(
        api_key=settings.mesh_api_key,
        model=settings.mesh_chat_model,
    )
    return RecommendationService(
        behavior_profile_service,
        semantic_retrieval_service,
        RecommendationRepository(db),
        build_recommendation_graph(recommendation_client),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    access_token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> User:
    """Resolve an active user from a bearer token or same-origin auth cookie."""
    token = credentials.credentials if credentials is not None else access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = decode_access_token(token)
        user_id = uuid.UUID(claims["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require the authenticated, persisted user to hold the admin role."""
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


__all__ = [
    "get_authentication_service",
    "get_current_user",
    "get_db",
    "get_event_service",
    "get_product_service",
    "get_product_vector_service",
    "get_recommendation_service",
    "get_user_service",
    "require_admin",
]
