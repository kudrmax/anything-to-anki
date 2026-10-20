"""A word stores when a card of it was last marked in review.

Revision ID: 0051
Revises: 0050

Existing words keep it empty: no time of marking was stored before.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("studied_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("studied_at")
