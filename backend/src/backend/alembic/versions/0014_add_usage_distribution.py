"""Add usage_distribution column to stored_candidates.

Revision ID: 0014
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("usage_distribution", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "usage_distribution")
