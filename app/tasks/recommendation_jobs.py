"""Background jobs that reuse the existing recommendation orchestration."""

from __future__ import annotations

import logging

from app.api.dependencies import build_recommendation_service
from app.database.session import SessionLocal
from app.repositories.user import UserRepository


logger = logging.getLogger(__name__)


def process_scheduled_recommendations() -> None:
    """Process every eligible user through the existing recommendation service."""
    session = SessionLocal()
    try:
        recipients = UserRepository(session).list_active_recommendation_recipients()
        recommendation_service = build_recommendation_service(session)
        for user in recipients:
            try:
                result = recommendation_service.generate_for_user(user.id)
            except Exception:
                session.rollback()
                logger.exception(
                    "Scheduled recommendation processing failed for user_id=%s",
                    user.id,
                )
                continue

            logger.info(
                "Scheduled recommendation processing completed for user_id=%s status=%s",
                user.id,
                result.status.value,
            )
    finally:
        session.close()
