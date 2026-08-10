"""Background jobs that reuse the existing recommendation orchestration."""

from __future__ import annotations

import logging

from app.api.dependencies import build_recommendation_service
from app.database.session import SessionLocal
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.services.email_service import DigestProduct, EmailService
from app.services.recommendation_service import RecommendationGenerationStatus


logger = logging.getLogger(__name__)


def process_scheduled_recommendations() -> None:
    """Process every eligible user through the existing recommendation service."""
    session = SessionLocal()
    try:
        recipients = UserRepository(session).list_active_recommendation_recipients()
        recommendation_service = build_recommendation_service(session)
        product_repository = ProductRepository(session)
        email_service = EmailService.from_settings()
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

            if result.status is not RecommendationGenerationStatus.GENERATED:
                logger.info(
                    "Scheduled recommendation processing completed for user_id=%s status=%s",
                    user.id,
                    result.status.value,
                )
                continue

            recommendation = result.recommendation
            if recommendation is None:
                logger.error(
                    "Scheduled recommendation generation returned no result for user_id=%s",
                    user.id,
                )
                continue
            if not email_service.is_configured:
                logger.warning(
                    "Scheduled recommendation email skipped for user_id=%s: SMTP is not configured",
                    user.id,
                )
                continue

            try:
                products = _resolve_digest_products(recommendation, product_repository, user.id)
                if not products:
                    logger.warning(
                        "Scheduled recommendation email skipped for user_id=%s: no valid products",
                        user.id,
                    )
                    continue
                delivered = email_service.send_recommendation_digest(
                    recipient_email=user.email,
                    narrative=recommendation.narrative,
                    products=products,
                )
            except Exception:
                logger.exception(
                    "Scheduled recommendation email preparation or delivery failed for user_id=%s",
                    user.id,
                )
                continue

            logger.info(
                "Scheduled recommendation processing completed for user_id=%s status=%s delivery=%s",
                user.id,
                result.status.value,
                "sent" if delivered else "not_sent",
            )
    finally:
        session.close()


def _resolve_digest_products(recommendation, product_repository: ProductRepository, user_id) -> list[DigestProduct]:
    """Resolve persisted product IDs to real catalog data for an email digest."""
    products: list[DigestProduct] = []
    for selection in recommendation.products:
        product = product_repository.get_by_id(selection.product_id)
        if product is None:
            logger.warning(
                "Scheduled recommendation email omitted missing product_id=%s for user_id=%s",
                selection.product_id,
                user_id,
            )
            continue
        products.append(
            DigestProduct(
                title=product.title,
                category=product.category,
                price=product.price,
                reason=selection.reason,
            )
        )
    return products
