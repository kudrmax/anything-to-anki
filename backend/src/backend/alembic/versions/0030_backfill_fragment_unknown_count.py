"""Backfill fragment_unknown_count from fragment_purity.

Revision ID: 0030
Revises: 0029

Existing candidates only know whether their phrase is clean or dirty, not how
many unknown words it has. A dirty phrase has at least one, so it gets 1:
enough to put it below clean phrases. Reprocessing the source computes the
real count.
"""
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE candidates SET fragment_unknown_count = 1 WHERE fragment_purity = 'dirty'"
    )


def downgrade() -> None:
    op.execute("UPDATE candidates SET fragment_unknown_count = 0")
