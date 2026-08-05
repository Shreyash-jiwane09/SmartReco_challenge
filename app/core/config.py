"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

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
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # API
    api_v1_prefix: str = "/api/v1"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str | None = "/openapi.json"

    # Database
    database_url: str = "postgresql://smartreco:smartreco@localhost:5432/smartreco"
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_timeout: int = Field(default=30, ge=1)
    database_pool_recycle: int = Field(default=1800, ge=0)

    # Security
    secret_key: str = Field(
        default="change-this-development-key-before-deployment",
        min_length=32,
        repr=False,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

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
