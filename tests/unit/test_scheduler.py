"""Focused tests for the optional APScheduler foundation."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.core import lifecycle
from app.core.config import Settings
from app.models.user import User, UserRole
from app.services.recommendation_service import RecommendationGenerationStatus
from app.tasks import recommendation_jobs
from app.tasks.scheduler import RECOMMENDATION_DAILY_DIGEST_JOB_ID, create_scheduler


def _config(**overrides: object) -> SimpleNamespace:
    return SimpleNamespace(
        recommendation_digest_hour=9,
        recommendation_digest_minute=0,
        recommendation_digest_timezone="UTC",
        **overrides,
    )


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql://smartreco:smartreco@localhost:5432/smartreco",
        secret_key="x" * 32,
        **overrides,
    )


def test_scheduler_configuration_defaults_to_disabled() -> None:
    settings = _settings()

    assert settings.scheduler_enabled is False
    assert settings.recommendation_digest_hour == 9
    assert settings.recommendation_digest_minute == 0
    assert settings.recommendation_digest_timezone == "UTC"


@pytest.mark.parametrize(
    ("field", "value"),
    [("recommendation_digest_hour", -1), ("recommendation_digest_hour", 24),
     ("recommendation_digest_minute", -1), ("recommendation_digest_minute", 60)],
)
def test_scheduler_configuration_rejects_invalid_cron_time(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        _settings(**{field: value})


def test_scheduler_registers_one_daily_cron_job_with_expected_configuration() -> None:
    scheduler = create_scheduler(config=_config(), job=lambda: None)  # type: ignore[arg-type]

    jobs = scheduler.get_jobs()

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == RECOMMENDATION_DAILY_DIGEST_JOB_ID
    assert str(job.trigger.timezone) == "UTC"
    assert "hour='9'" in str(job.trigger)
    assert "minute='0'" in str(job.trigger)
    assert job.max_instances == 1
    assert job.coalesce is True


def test_lifespan_does_not_create_scheduler_when_disabled(monkeypatch) -> None:
    factory_calls: list[object] = []
    monkeypatch.setattr(lifecycle, "settings", SimpleNamespace(scheduler_enabled=False))
    monkeypatch.setattr(lifecycle, "create_scheduler", lambda: factory_calls.append(object()))

    async def run() -> None:
        async with lifecycle.lifespan(FastAPI()):
            pass

    asyncio.run(run())

    assert factory_calls == []


def test_lifespan_starts_and_stops_scheduler_when_enabled(monkeypatch) -> None:
    scheduler = SimpleNamespace(start_calls=0, shutdown_calls=[])
    scheduler.start = lambda: setattr(scheduler, "start_calls", scheduler.start_calls + 1)
    scheduler.shutdown = lambda **kwargs: scheduler.shutdown_calls.append(kwargs)
    app = FastAPI()
    monkeypatch.setattr(lifecycle, "settings", SimpleNamespace(scheduler_enabled=True))
    monkeypatch.setattr(lifecycle, "create_scheduler", lambda: scheduler)

    async def run() -> None:
        async with lifecycle.lifespan(app):
            assert app.state.scheduler is scheduler
            assert scheduler.start_calls == 1

    asyncio.run(run())

    assert scheduler.shutdown_calls == [{"wait": False}]


class _Session:
    def __init__(self) -> None:
        self.closed = False
        self.rollbacks = 0

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


class _UserRepository:
    def __init__(self, _session, users: list[User]) -> None:
        self.users = users

    def list_active_recommendation_recipients(self) -> list[User]:
        return self.users


class _RecommendationService:
    def __init__(self, results: dict, failing_user_id=None) -> None:
        self.results = results
        self.failing_user_id = failing_user_id
        self.calls: list[object] = []

    def generate_for_user(self, user_id):
        self.calls.append(user_id)
        if user_id == self.failing_user_id:
            raise RuntimeError("unexpected failure")
        return SimpleNamespace(status=self.results[user_id])


@pytest.mark.parametrize(
    "status",
    [
        RecommendationGenerationStatus.TRIGGER_NOT_MET,
        RecommendationGenerationStatus.NO_PRODUCTS,
        RecommendationGenerationStatus.GENERATED,
    ],
)
def test_job_reuses_recommendation_service_for_each_outcome(monkeypatch, status) -> None:
    user = User(id=uuid4(), email="recipient@example.com", hashed_password="hash", full_name="User")
    session = _Session()
    service = _RecommendationService({user.id: status})
    monkeypatch.setattr(recommendation_jobs, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        recommendation_jobs,
        "UserRepository",
        lambda current_session: _UserRepository(current_session, [user]),
    )
    monkeypatch.setattr(recommendation_jobs, "build_recommendation_service", lambda current_session: service)

    recommendation_jobs.process_scheduled_recommendations()

    assert service.calls == [user.id]
    assert session.closed is True
    assert session.rollbacks == 0


def test_job_rolls_back_logs_and_continues_after_one_user_failure(monkeypatch, caplog) -> None:
    failed_user = User(id=uuid4(), email="failed@example.com", hashed_password="hash", full_name="Failed")
    next_user = User(id=uuid4(), email="next@example.com", hashed_password="hash", full_name="Next")
    session = _Session()
    service = _RecommendationService(
        {next_user.id: RecommendationGenerationStatus.GENERATED},
        failing_user_id=failed_user.id,
    )
    monkeypatch.setattr(recommendation_jobs, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        recommendation_jobs,
        "UserRepository",
        lambda current_session: _UserRepository(current_session, [failed_user, next_user]),
    )
    monkeypatch.setattr(recommendation_jobs, "build_recommendation_service", lambda current_session: service)

    with caplog.at_level("ERROR"):
        recommendation_jobs.process_scheduled_recommendations()

    assert service.calls == [failed_user.id, next_user.id]
    assert session.rollbacks == 1
    assert session.closed is True
    assert "failed for user_id" in caplog.text
