"""drop legacy upgrade_schema artefacts

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-09

Removes the parallel `upgrade_schema()` system from `database.py`. That
function used to run inline `ALTER TABLE` / `CREATE TABLE IF NOT EXISTS`
statements after `run_alembic_migrations`. Of its 13 operations, only one
(the settings rename) was still doing useful work; the rest were either
duplicates of what `0001_initial_schema` already creates from current models,
or zombie operations recreating tables that `0006_drop_legacy_job_tables`
had just dropped.

This revision applies the only live operation as a proper Alembic data
migration, then cleans up the leftovers that `upgrade_schema` had been
silently producing on every startup since `0006`:

  * Drops zombie tables `generation_jobs`, `media_extraction_jobs` if they
    still exist on the live DB (they were recreated empty after each start
    by the old `upgrade_schema`).
  * Drops orphan columns `candidates.ai_meaning`, `candidates.definition`
    if they still exist (added by `upgrade_schema`, never used by the code).

All operations are idempotent: they introspect the current schema and skip
work that does not apply. On a fresh DB built from the current models the
revision is effectively a no-op.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Settings data migration: rename anki_field_screenshot → anki_field_image.
    #    Was the only live operation in the old upgrade_schema. Idempotent: the
    #    NOT EXISTS guard prevents primary-key conflict if the new key is
    #    already present, and the DELETE removes any leftover legacy row.
    if _table_exists("settings"):
        bind.execute(text(
            "UPDATE settings SET key = 'anki_field_image' "
            "WHERE key = 'anki_field_screenshot' "
            "AND NOT EXISTS (SELECT 1 FROM settings WHERE key = 'anki_field_image')"
        ))
        bind.execute(text(
            "DELETE FROM settings WHERE key = 'anki_field_screenshot'"
        ))

    # 2. Drop zombie tables. 0006 dropped these once; upgrade_schema then
    #    silently recreated them empty on every startup. Now they go for good.
    if _table_exists("generation_jobs"):
        op.drop_table("generation_jobs")
    if _table_exists("media_extraction_jobs"):
        op.drop_table("media_extraction_jobs")

    # 3. Drop orphan columns from `candidates`. Added by upgrade_schema, never
    #    referenced anywhere in the codebase. SQLite needs batch_alter_table
    #    (table rebuild) for column drops.
    orphan_columns = [
        c for c in ("ai_meaning", "definition")
        if _column_exists("candidates", c)
    ]
    if orphan_columns:
        with op.batch_alter_table("candidates") as batch_op:
            for col in orphan_columns:
                batch_op.drop_column(col)


def downgrade() -> None:
    # Intentionally no-op: this revision removes dead artefacts. Recreating
    # zombie tables and orphan columns serves no purpose. Same approach as
    # 0001_initial_schema.downgrade.
    pass
