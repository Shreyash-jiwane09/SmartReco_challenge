"""Add recommendation persistence tables.

Revision ID: d4f2b6c8e1a3
Revises: c3e9a1b7d2f4
Create Date: 2026-08-09 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d4f2b6c8e1a3"
down_revision: str | None = "c3e9a1b7d2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create recommendations and their ordered Product associations."""
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_user_id", "recommendations", ["user_id"])
    op.create_table(
        "recommendation_products",
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("recommendation_id", "product_id"),
    )


def downgrade() -> None:
    """Drop recommendation persistence tables cleanly."""
    op.drop_table("recommendation_products")
    op.drop_index("ix_recommendations_user_id", table_name="recommendations")
    op.drop_table("recommendations")
