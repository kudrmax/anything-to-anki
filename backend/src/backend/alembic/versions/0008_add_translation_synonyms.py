"""add translation and synonyms columns to candidate_meanings

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-08
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _column_exists("candidate_meanings", "translation"):
        op.add_column(
            "candidate_meanings",
            sa.Column("translation", sa.Text(), nullable=True),
        )
    if not _column_exists("candidate_meanings", "synonyms"):
        op.add_column(
            "candidate_meanings",
            sa.Column("synonyms", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("candidate_meanings", "synonyms")
    op.drop_column("candidate_meanings", "translation")
