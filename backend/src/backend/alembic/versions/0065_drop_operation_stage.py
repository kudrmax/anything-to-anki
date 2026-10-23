"""`source_operations.stage` goes: processing runs as a long operation now, under the long
operation lock, and no longer holds its source or tells its stage there.

Revision ID: 0065
Revises: 0064
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("source_operations") as batch:
        batch.drop_column("stage")


def downgrade() -> None:
    with op.batch_alter_table("source_operations") as batch:
        batch.add_column(sa.Column("stage", sa.String(30), nullable=True))
