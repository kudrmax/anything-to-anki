"""Tie enrichment to its candidate and never reuse candidate ids.

Revision ID: 0025
Revises: 0024

Meanings, media, pronunciations, TTS and Anki sync marks had no foreign key
to candidates, so deleting candidates (reprocess, delete source) left them
behind. SQLite then handed the freed id to a new candidate, which inherited
another word's enrichment.

1. Remember the highest candidate id ever referenced, orphans included.
2. Delete the orphan rows, and media, pronunciation and TTS rows whose files
   live in another source's media folder — those were inherited through a
   reused id and belong to a different word.
3. Rebuild the enrichment tables with ON DELETE CASCADE to candidates.
4. Rebuild candidates with AUTOINCREMENT and ON DELETE CASCADE to sources,
   starting the sequence after the remembered id.

Tables are rebuilt with foreign keys disabled (the Alembic connection never
enables them), otherwise dropping the old candidates table would cascade.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.engine import Connection

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILD_TABLES = (
    "candidate_meanings",
    "candidate_media",
    "candidate_pronunciations",
    "candidate_tts",
    "anki_synced_cards",
)
_TABLES_REFERENCING_CANDIDATES = (*_CHILD_TABLES, "cefr_breakdowns", "jobs")
_CANDIDATES_SOURCE_FK = "fk_candidates_source_id_sources"
_FILE_COLUMNS: dict[str, tuple[str, ...]] = {
    "candidate_media": ("screenshot_path", "audio_path"),
    "candidate_pronunciations": ("us_audio_path", "uk_audio_path"),
    "candidate_tts": ("audio_path",),
}


def _child_fk_name(table: str) -> str:
    return f"fk_{table}_candidate_id_candidates"


def _highest_candidate_id_ever(conn: Connection) -> int:
    referenced = " UNION ALL ".join(
        f"SELECT MAX(candidate_id) AS id FROM {table}"
        for table in _TABLES_REFERENCING_CANDIDATES
    )
    highest = conn.execute(sa.text(
        f"SELECT MAX(id) FROM (SELECT MAX(id) AS id FROM candidates UNION ALL {referenced})"
    )).scalar()
    return int(highest or 0)


def _delete_files_of_other_sources(conn: Connection) -> None:
    for table, columns in _FILE_COLUMNS.items():
        foreign = " OR ".join(
            f"({column} IS NOT NULL AND {column} NOT LIKE '%/media/' || c.source_id || '/%')"
            for column in columns
        )
        conn.execute(sa.text(
            f"""
            DELETE FROM {table} WHERE candidate_id IN (
                SELECT t.candidate_id FROM {table} t
                JOIN candidates c ON c.id = t.candidate_id
                WHERE {foreign}
            )
            """
        ))


def _ensure_foreign_keys_disabled(conn: Connection) -> None:
    if conn.execute(sa.text("PRAGMA foreign_keys")).scalar():
        msg = "0025 must run with PRAGMA foreign_keys=OFF: rebuilding candidates would cascade"
        raise RuntimeError(msg)


def upgrade() -> None:
    conn = op.get_bind()
    _ensure_foreign_keys_disabled(conn)
    highest_id = _highest_candidate_id_ever(conn)

    for table in _TABLES_REFERENCING_CANDIDATES:
        op.execute(
            f"DELETE FROM {table} WHERE candidate_id NOT IN (SELECT id FROM candidates)"
        )
    _delete_files_of_other_sources(conn)

    for table in _CHILD_TABLES:
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.create_foreign_key(
                _child_fk_name(table), "candidates", ["candidate_id"], ["id"],
                ondelete="CASCADE",
            )

    with op.batch_alter_table(
        "candidates", recreate="always", table_kwargs={"sqlite_autoincrement": True},
    ) as batch_op:
        batch_op.create_foreign_key(
            _CANDIDATES_SOURCE_FK, "sources", ["source_id"], ["id"], ondelete="CASCADE",
        )

    conn.execute(sa.text("DELETE FROM sqlite_sequence WHERE name = 'candidates'"))
    conn.execute(
        sa.text("INSERT INTO sqlite_sequence (name, seq) VALUES ('candidates', :seq)"),
        {"seq": highest_id},
    )


def downgrade() -> None:
    _ensure_foreign_keys_disabled(op.get_bind())

    with op.batch_alter_table(
        "candidates", recreate="always", table_kwargs={"sqlite_autoincrement": False},
    ) as batch_op:
        batch_op.drop_constraint(_CANDIDATES_SOURCE_FK, type_="foreignkey")

    for table in _CHILD_TABLES:
        with op.batch_alter_table(table, recreate="always") as batch_op:
            batch_op.drop_constraint(_child_fk_name(table), type_="foreignkey")
