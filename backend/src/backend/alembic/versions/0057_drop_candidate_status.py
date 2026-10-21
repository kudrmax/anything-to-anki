"""Drop `candidates.status`, the stored copy of a word's decision status (spec §2). The
rules read the decision from the facts, the decision card and its active binding; the
screens read it from `word_states`, the projection.

Revision ID: 0057
Revises: 0056

`ix_candidates_lower_lemma` named the column, and SQLite drops no column an index names, so
it goes first and comes back on the lower-case lemma alone: the projector's lookup of a
lemma's words in every source. The words waiting for export, which the knowledge snapshot
read through it, are read from their Learn and Cloze cards by a partial index of those.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

LEMMA_INDEX = "ix_candidates_lower_lemma"
AWAITING_EXPORT_INDEX = "ix_phrases_awaiting_export"


def upgrade() -> None:
    op.drop_index(LEMMA_INDEX, table_name="candidates")
    op.execute("ALTER TABLE candidates DROP COLUMN status")
    op.create_index(LEMMA_INDEX, "candidates", [sa.text("lower(lemma)")])
    op.create_index(
        AWAITING_EXPORT_INDEX, "phrases", ["candidate_id"],
        sqlite_where=sa.text("choice IN ('learn', 'cloze')"),
    )


def downgrade() -> None:
    raise NotImplementedError("the decision status is read from the facts; nothing to restore")
