"""add examples column to candidate_meanings

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-10

Adds the `examples` TEXT column to `candidate_meanings` table.
Nullable — existing rows will have NULL which is fine (legacy compat).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _column_exists("candidate_meanings", "examples"):
        with op.batch_alter_table("candidate_meanings") as batch_op:
            batch_op.add_column(sa.Column("examples", sa.Text, nullable=True))


def downgrade() -> None:
    if _column_exists("candidate_meanings", "examples"):
        with op.batch_alter_table("candidate_meanings") as batch_op:
            batch_op.drop_column("examples")
