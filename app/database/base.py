"""Shared SQLAlchemy declarative base for SmartReco models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SmartReco SQLAlchemy models."""
