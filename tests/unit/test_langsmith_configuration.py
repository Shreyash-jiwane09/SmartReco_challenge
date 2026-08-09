"""Configuration safety tests for optional LangSmith tracing."""

from __future__ import annotations

import os

from app.core.config import Settings, configure_langsmith_environment


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql://smartreco:smartreco@localhost:5432/smartreco",
        secret_key="x" * 32,
        **overrides,
    )


def test_langsmith_tracing_defaults_to_disabled_without_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    settings = _settings()

    assert settings.langsmith_tracing is False
    assert settings.langsmith_api_key == ""
    assert settings.langsmith_project == "smartreco"


def test_disabled_langsmith_configuration_does_not_export_sdk_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    configure_langsmith_environment(_settings(langsmith_tracing=False))

    assert os.getenv("LANGSMITH_TRACING") is None
    assert os.getenv("LANGSMITH_API_KEY") is None
    assert os.getenv("LANGSMITH_PROJECT") is None
