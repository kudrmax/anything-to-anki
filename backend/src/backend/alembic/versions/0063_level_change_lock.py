"""`level_change_lock`: present while the level is being changed. Every process sees it,
so no write but the level change's own goes through meanwhile.

Revision ID: 0063
Revises: 0062
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "level_change_lock",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_level_change_lock_single"),
    )


def downgrade() -> None:
    op.drop_table("level_change_lock")
