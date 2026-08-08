"""Make event resource type nullable.

Revision ID: c3e9a1b7d2f4
Revises: 8f2c1a7b4d90
Create Date: 2026-08-08 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3e9a1b7d2f4"
down_revision: str | None = "8f2c1a7b4d90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow behavioral events without a target resource type."""
    op.alter_column(
        "events",
        "resource_type",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    """Require a target resource type again."""
    op.alter_column(
        "events",
        "resource_type",
        existing_type=sa.String(length=100),
        nullable=False,
    )
