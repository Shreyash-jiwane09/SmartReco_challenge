"""Centralized application logging configuration."""

from __future__ import annotations

import logging
import sys

from app.core.config import get_settings


_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_HANDLER_MARKER = "_smartreco_console_handler"


def configure_logging() -> None:
    """Configure application-wide console logging."""
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = logging.getLevelNamesMapping().get(level_name)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {settings.log_level!r}")

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)
    console_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if getattr(handler, _HANDLER_MARKER, False)
        ),
        None,
    )

    if console_handler is None:
        console_handler = logging.StreamHandler(sys.stdout)
        setattr(console_handler, _HANDLER_MARKER, True)
        root_logger.addHandler(console_handler)

    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)


def get_logger(name: str) -> logging.Logger:
    """Return a named standard-library logger."""
    return logging.getLogger(name)
