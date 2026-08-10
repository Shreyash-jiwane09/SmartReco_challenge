"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
import os
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, environment-backed settings for the SmartReco API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "SmartReco"
    app_version: str = "0.7.0"
    environment: Literal["development", "testing", "staging", "production"] = "development"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    # Database
    database_url: str
    database_echo: bool = False

    # AI / vector search
    mesh_api_key: str = Field(default="", repr=False)
    mesh_embedding_model: str = "sentence-transformers/all-minilm-l6-v2"
    mesh_chat_model: str = "openai/gpt-4o-mini"
    chroma_collection_name: str = "smartreco_products"
    chroma_persist_directory: str = "./data/chroma"

    # Optional LangSmith observability. Tracing never participates in
    # recommendation correctness and is disabled unless explicitly enabled.
    langsmith_tracing: bool = False
    langsmith_api_key: str = Field(default="", repr=False)
    langsmith_project: str = "smartreco"

    # Scheduled recommendation processing. Disabled unless explicitly enabled.
    recommendation_digest_hour: int = Field(default=9, ge=0, le=23)
    recommendation_digest_minute: int = Field(default=0, ge=0, le=59)
    recommendation_digest_timezone: str = "UTC"
    scheduler_enabled: bool = False

    # Optional SMTP delivery for scheduled recommendation digests.
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = Field(default="", repr=False)
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = Field(default=10, ge=1)

    # Security
    secret_key: str = Field(min_length=32, repr=False)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )
    cors_allow_headers: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID"]
    )

    @field_validator("cors_origins", "cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def parse_list_setting(cls, value: Any) -> Any:
        """Allow CORS lists to be configured as JSON or comma-separated values."""
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide cached application settings instance."""
    return Settings()


def configure_langsmith_environment(config: Settings) -> None:
    """Expose enabled Pydantic settings to LangGraph and LangSmith SDKs.

    The SDKs read ``os.environ`` directly, while this application also supports
    values in its local ``.env`` file through Pydantic. Nothing is exported
    unless tracing is explicitly enabled, so normal application execution has
    no LangSmith configuration or network dependency.
    """
    if not config.langsmith_tracing:
        return

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    if config.langsmith_api_key:
        os.environ.setdefault("LANGSMITH_API_KEY", config.langsmith_api_key)
    if config.langsmith_project:
        os.environ.setdefault("LANGSMITH_PROJECT", config.langsmith_project)


settings = get_settings()
configure_langsmith_environment(settings)

