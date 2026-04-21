"""Add has_custom_context_fragment to candidates.

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("has_custom_context_fragment", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("candidates", "has_custom_context_fragment")
