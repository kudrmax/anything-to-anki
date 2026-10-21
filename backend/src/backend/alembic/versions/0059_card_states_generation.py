"""`card_states` keeps what the ✨ menu counts: the sections a card would stand in open at
every threshold step, what generation made for it, and whether a clip can be cut for it;
three covering indexes serve the counts of the review header and of the ✨ menu.

The rows are computed anew by the rebuild at every start, before any request: the values
written here only fill the new NOT NULL columns of the rows already stored.

Revision ID: 0059
Revises: 0058
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_FLAGS = (
    "polish_done", "meaning_done", "media_done", "tts_done", "pronunciation_done",
    "media_timed",
)


def upgrade() -> None:
    op.add_column(
        "card_states", sa.Column("open_sections", sa.Text(), nullable=False, server_default=""),
    )
    op.execute("UPDATE card_states SET open_sections = sections")
    for flag in _FLAGS:
        op.add_column(
            "card_states", sa.Column(flag, sa.Boolean(), nullable=False, server_default="0"),
        )
    op.create_index(
        "ix_card_states_source_removed_sections", "card_states",
        ["source_id", "removed", "sections"],
    )
    op.create_index(
        "ix_card_states_generation", "card_states",
        [
            "source_id", "removed", "wants_generation", "open_sections", "polish_done",
            "meaning_done", "media_done", "tts_done", "pronunciation_done", "media_timed",
        ],
    )
    op.create_index(
        "ix_card_states_words_in_play", "card_states",
        ["source_id", "removed", "wants_generation", "word_id"],
    )


def downgrade() -> None:
    for index in (
        "ix_card_states_words_in_play", "ix_card_states_generation",
        "ix_card_states_source_removed_sections",
    ):
        op.drop_index(index, table_name="card_states")
    for column in (*_FLAGS, "open_sections"):
        op.drop_column("card_states", column)
