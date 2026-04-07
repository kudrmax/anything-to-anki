"""add anki_synced_cards table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-07

Tracks which candidates have been successfully added to Anki.
A record in this table means the candidate was synced without errors.
candidate_id is UNIQUE — one candidate maps to at most one Anki note.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anki_synced_cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("candidate_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("anki_note_id", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("anki_synced_cards")
