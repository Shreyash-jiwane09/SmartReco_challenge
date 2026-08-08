"""Behavioral event ingestion endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user, get_event_service
from app.models.user import User
from app.schemas.event import EventBatchSchema, EventResponseSchema
from app.services.event_service import EventService


router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def ingest_events(
    payload: EventBatchSchema,
    current_user: User = Depends(get_current_user),
    service: EventService = Depends(get_event_service),
) -> EventResponseSchema:
    """Persist one authenticated batch of behavioral events."""
    if payload.session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Events can only be submitted for the authenticated user",
        )

    persisted_events = service.create_many(payload)
    return EventResponseSchema(accepted=True, received=len(persisted_events))
