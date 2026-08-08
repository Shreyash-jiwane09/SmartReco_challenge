"""PostgreSQL-backed test fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.database.base import Base
import app.models  # noqa: F401 -- register all mapped tables with Base metadata.


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated PostgreSQL schema and synchronous test session."""
    database_url = os.getenv("TEST_DATABASE_URL", settings.database_url)
    schema_name = f"smartreco_test_{uuid4().hex}"
    admin_engine = create_engine(database_url)

    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema_name))

    test_engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )
    try:
        Base.metadata.create_all(test_engine)
        session = sessionmaker(bind=test_engine, expire_on_commit=False)()
        try:
            yield session
        finally:
            session.rollback()
            session.close()
    finally:
        test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema_name, cascade=True))
        admin_engine.dispose()
