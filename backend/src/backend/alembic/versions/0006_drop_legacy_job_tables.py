"""drop legacy in-process job tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-07

Phase 2: the in-process job system is replaced by ARQ + Redis.
The job tables are no longer used by any code.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("generation_jobs"):
        op.drop_table("generation_jobs")
    if _table_exists("media_extraction_jobs"):
        op.drop_table("media_extraction_jobs")


def downgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("processed_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "media_extraction_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_candidates", sa.Integer(), nullable=False),
        sa.Column("processed_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
