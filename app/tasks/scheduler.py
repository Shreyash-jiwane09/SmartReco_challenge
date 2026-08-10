"""In-process APScheduler configuration for scheduled recommendation processing."""

from __future__ import annotations

from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings, settings
from app.tasks.recommendation_jobs import process_scheduled_recommendations


RECOMMENDATION_DAILY_DIGEST_JOB_ID = "recommendation_daily_digest"


def create_scheduler(
    *,
    config: Settings = settings,
    job: Callable[[], None] = process_scheduled_recommendations,
) -> AsyncIOScheduler:
    """Build the one in-memory daily recommendation-processing scheduler.

    This scheduler is process-local. Enable it in only one application process
    or replica when deploying with multiple workers.
    """
    scheduler = AsyncIOScheduler(timezone=config.recommendation_digest_timezone)
    scheduler.add_job(
        job,
        trigger="cron",
        id=RECOMMENDATION_DAILY_DIGEST_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        hour=config.recommendation_digest_hour,
        minute=config.recommendation_digest_minute,
        timezone=config.recommendation_digest_timezone,
    )
    return scheduler
