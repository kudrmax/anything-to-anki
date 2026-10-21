"""`card_states` keeps what the queue holds for each card, per kind of generation: no job,
a failed one or one on its way. The ✨ counts then group the cards alone, in the order of
their covering index, however long the queue is.

The rows are computed anew by the rebuild at every start, before any request: the zeros
written here only fill the new NOT NULL columns of the rows already stored.

Revision ID: 0060
Revises: 0059
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

_JOBS = ("polish_job", "meaning_job", "media_job", "tts_job", "pronunciation_job")
_GENERATION = (
    "source_id", "removed", "wants_generation", "open_sections", "polish_done",
    "meaning_done", "media_done", "tts_done", "pronunciation_done", "media_timed",
)
_INDEX = "ix_card_states_generation"


def upgrade() -> None:
    for column in _JOBS:
        op.add_column(
            "card_states",
            sa.Column(column, sa.Integer(), nullable=False, server_default="0"),
        )
    op.drop_index(_INDEX, table_name="card_states")
    op.create_index(_INDEX, "card_states", [*_GENERATION, *_JOBS])


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="card_states")
    op.create_index(_INDEX, "card_states", list(_GENERATION))
    for column in _JOBS:
        op.drop_column("card_states", column)
