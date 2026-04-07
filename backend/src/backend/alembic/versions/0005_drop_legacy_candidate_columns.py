"""drop legacy meaning/media columns from candidates

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-07

Phase 1, step 3: now that data lives in candidate_meanings and candidate_media,
drop the deprecated columns from candidates. Uses batch_alter_table because
SQLite needs table recreation for column drops.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_columns_present() -> bool:
    """Return True if at least one legacy column still exists in candidates."""
    from sqlalchemy import inspect, text

    bind = op.get_bind()
    rows = bind.execute(text("PRAGMA table_info(candidates)")).fetchall()
    existing = {row[1] for row in rows}
    legacy = {"meaning", "ipa", "screenshot_path", "audio_path", "media_start_ms", "media_end_ms"}
    return bool(existing & legacy)


def upgrade() -> None:
    if not _legacy_columns_present():
        # Fresh DB — columns never existed (0001 built candidates from current
        # models which already lack them). Nothing to drop.
        return

    with op.batch_alter_table("candidates") as batch_op:
        batch_op.drop_column("meaning")
        batch_op.drop_column("ipa")
        batch_op.drop_column("screenshot_path")
        batch_op.drop_column("audio_path")
        batch_op.drop_column("media_start_ms")
        batch_op.drop_column("media_end_ms")


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("candidates") as batch_op:
        batch_op.add_column(sa.Column("meaning", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ipa", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("screenshot_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("audio_path", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("media_start_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("media_end_ms", sa.Integer(), nullable=True))
