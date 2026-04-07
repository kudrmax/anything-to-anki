"""add candidate_meanings and candidate_media tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-07

Phase 1, step 1: create new tables for the meaning and media enrichments.
This migration only creates the tables (empty). Data migration from the
old `candidates.meaning` / `candidates.screenshot_path` / etc. columns
happens in 0004. Old columns are dropped in 0005.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_meanings",
        sa.Column("candidate_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column("ipa", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="done"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "candidate_media",
        sa.Column("candidate_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("screenshot_path", sa.Text(), nullable=True),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("start_ms", sa.Integer(), nullable=True),
        sa.Column("end_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="done"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("candidate_media")
    op.drop_table("candidate_meanings")
