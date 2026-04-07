"""migrate candidate enrichment data into new tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-07

Phase 1, step 2: copy meaning/ipa and media data from `candidates` columns
into the new `candidate_meanings` and `candidate_media` tables. The old
columns are dropped in 0005.

Idempotent: uses INSERT OR IGNORE so re-running on a partially migrated DB
is safe.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn: object, table: str, column: str) -> bool:
    """Return True if *column* exists in *table* (SQLite PRAGMA-based check)."""
    from sqlalchemy import text as _text

    rows = conn.execute(_text(f"PRAGMA table_info({table})")).fetchall()  # type: ignore[union-attr]
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # On a fresh DB (migrated from scratch) these columns never existed —
    # 0001 created candidates from the *current* models which already lack them.
    # Only run the INSERT when the legacy column is actually present.
    if _column_exists(conn, "candidates", "meaning"):
        # 1. Copy meanings: every candidate that has meaning IS NOT NULL
        conn.execute(text(
            """
            INSERT OR IGNORE INTO candidate_meanings
                (candidate_id, meaning, ipa, status, error, generated_at)
            SELECT id, meaning, ipa, 'done', NULL, NULL
            FROM candidates
            WHERE meaning IS NOT NULL
            """
        ))

    if _column_exists(conn, "candidates", "screenshot_path"):
        # 2. Copy media: every candidate that has any media data
        conn.execute(text(
            """
            INSERT OR IGNORE INTO candidate_media
                (candidate_id, screenshot_path, audio_path, start_ms, end_ms,
                 status, error, generated_at)
            SELECT id, screenshot_path, audio_path, media_start_ms, media_end_ms,
                   'done', NULL, NULL
            FROM candidates
            WHERE screenshot_path IS NOT NULL
               OR audio_path IS NOT NULL
               OR media_start_ms IS NOT NULL
            """
        ))


def downgrade() -> None:
    # Inverse: copy back into candidates columns. Assumes 0005 has been
    # downgraded first (so the columns still exist).
    conn = op.get_bind()
    conn.execute(text("""
        UPDATE candidates
        SET meaning = (SELECT meaning FROM candidate_meanings
                       WHERE candidate_id = candidates.id),
            ipa = (SELECT ipa FROM candidate_meanings
                   WHERE candidate_id = candidates.id)
    """))
    conn.execute(text("""
        UPDATE candidates
        SET screenshot_path = (SELECT screenshot_path FROM candidate_media
                                WHERE candidate_id = candidates.id),
            audio_path = (SELECT audio_path FROM candidate_media
                           WHERE candidate_id = candidates.id),
            media_start_ms = (SELECT start_ms FROM candidate_media
                               WHERE candidate_id = candidates.id),
            media_end_ms = (SELECT end_ms FROM candidate_media
                             WHERE candidate_id = candidates.id)
    """))
    conn.execute(text("DELETE FROM candidate_meanings"))
    conn.execute(text("DELETE FROM candidate_media"))
