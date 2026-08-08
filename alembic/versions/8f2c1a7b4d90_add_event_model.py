"""Add behavioral event model.

Revision ID: 8f2c1a7b4d90
Revises: e2a76e806994
Create Date: 2026-08-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8f2c1a7b4d90"
down_revision: str | None = "e2a76e806994"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


event_type = postgresql.ENUM(
    "PRODUCT_VIEW",
    "SEARCH",
    "CLICK",
    "TIME_SPENT",
    name="event_type",
    create_type=False,
)


def upgrade() -> None:
    """Create the behavioral events table and supporting indexes."""
    bind = op.get_bind()
    event_type.create(bind, checkfirst=True)

    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column(
            "event_type",
            event_type,
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("page_url", sa.String(length=2048), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"], unique=False)
    op.create_index(
        "ix_events_session_id",
        "events",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_events_event_type",
        "events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_events_event_timestamp",
        "events",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_events_user_id_event_timestamp",
        "events",
        ["user_id", "event_timestamp"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the behavioral events table and its enum type."""
    op.drop_index("ix_events_user_id_event_timestamp", table_name="events")
    op.drop_index("ix_events_event_timestamp", table_name="events")
    op.drop_index("ix_events_event_type", table_name="events")
    op.drop_index("ix_events_session_id", table_name="events")
    op.drop_index("ix_events_user_id", table_name="events")
    op.drop_table("events")
    event_type.drop(op.get_bind(), checkfirst=True)
