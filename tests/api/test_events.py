"""API tests for batched behavioral event ingestion."""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user
from app.api.v1.events import ingest_events, router
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.event import EventBatchSchema


def _payload(user_id: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "session": {"user_id": user_id, "session_id": "session-1"},
        "client": {},
        "events": [
            {
                "event_type": "PRODUCT_VIEW",
                "resource_type": "product",
                "resource_id": "product-1",
                "event_timestamp": timestamp,
                "metadata": {},
            },
            {
                "event_type": "SEARCH",
                "event_timestamp": timestamp,
                "metadata": {"query": "running shoes"},
            },
        ],
    }


def test_ingest_events_persists_one_authenticated_batch() -> None:
    user = User(
        id=uuid4(),
        email="events@example.com",
        hashed_password="hash",
        full_name="Events",
        is_active=True,
    )
    batch = EventBatchSchema.model_validate(_payload(str(user.id)))
    service = type("EventServiceStub", (), {"create_many": lambda self, value: value.events})()

    response = ingest_events(batch, user, service)

    assert response.accepted is True
    assert response.received == 2


def test_ingest_events_rejects_a_batch_for_another_user() -> None:
    user = User(
        id=uuid4(),
        email="events@example.com",
        hashed_password="hash",
        full_name="Events",
        is_active=True,
    )
    batch = EventBatchSchema.model_validate(_payload(str(uuid4())))
    service = type("EventServiceStub", (), {"create_many": lambda self, value: value.events})()

    with pytest.raises(HTTPException) as exc_info:
        ingest_events(batch, user, service)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == (
        "Events can only be submitted for the authenticated user"
    )


def test_events_router_is_registered_at_the_versioned_events_path() -> None:
    assert router.prefix == "/events"
    assert router.routes[0].path == "/events"
    assert router.routes[0].status_code == 201


def test_current_user_is_resolved_from_a_valid_bearer_token() -> None:
    user = User(
        id=uuid4(),
        email="events@example.com",
        hashed_password="hash",
        full_name="Events",
        is_active=True,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    session = Mock()
    session.execute.return_value = result
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=create_access_token(str(user.id)),
    )

    assert get_current_user(credentials, session) is user


def test_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None, Mock())

    assert exc_info.value.status_code == 401


def test_current_user_is_resolved_from_the_browser_auth_cookie() -> None:
    user = User(
        id=uuid4(),
        email="cookie-events@example.com",
        hashed_password="hash",
        full_name="Cookie Events",
        is_active=True,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = user
    session = Mock()
    session.execute.return_value = result

    assert get_current_user(None, session, create_access_token(str(user.id))) is user
