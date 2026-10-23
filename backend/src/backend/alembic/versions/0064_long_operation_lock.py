"""`long_operation_lock` instead of `level_change_lock`: the same lock now kept by every long
operation over sources, not only the level change. A lock is never held across a start, so
the old table goes and the new one starts empty.

Revision ID: 0064
Revises: 0063
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("level_change_lock")
    op.create_table(
        "long_operation_lock",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_long_operation_lock_single"),
    )


def downgrade() -> None:
    op.drop_table("long_operation_lock")
    op.create_table(
        "level_change_lock",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_level_change_lock_single"),
    )
