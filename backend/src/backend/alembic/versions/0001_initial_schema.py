"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-07

Baseline: creates the four core tables with the schema as of 0001.
All column/table definitions are static — later migrations apply incremental changes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("cleaned_text", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("processing_stage", sa.String(30), nullable=True),
        sa.Column("video_path", sa.Text, nullable=True),
        sa.Column("audio_track_index", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=False),
        sa.Column("cefr_level", sa.String(10), nullable=False),
        sa.Column("zipf_frequency", sa.Float, nullable=False),
        sa.Column("is_sweet_spot", sa.Boolean, nullable=False),
        sa.Column("context_fragment", sa.Text, nullable=False),
        sa.Column("fragment_purity", sa.String(10), nullable=False),
        sa.Column("occurrences", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("surface_form", sa.String(100), nullable=True),
        sa.Column("is_phrasal_verb", sa.Boolean, nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_candidates_source_id", "candidates", ["source_id"])

    op.create_table(
        "known_words",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("lemma", "pos", name="uq_known_word_lemma_pos"),
    )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.String(200), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("known_words")
    op.drop_index("ix_candidates_source_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("sources")
