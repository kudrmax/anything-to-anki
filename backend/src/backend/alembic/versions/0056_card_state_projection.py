"""The stored projection of card state: card_states, word_states, phrase_words and the
revision counter in projection_meta (spec §5), and the index of words by lower-case lemma
the projector reads them by. The tables start empty: the app fills them by a full rebuild
at every start, before it takes requests.

Revision ID: 0056
Revises: 0055

The rows are derived, so no foreign keys: a card that goes away stays as a `removed`
tombstone written by the projector.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

META_ID = 1
FIRST_REVISION = 0


def upgrade() -> None:
    op.create_table(
        "card_states",
        sa.Column("phrase_id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("lemma", sa.Text(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        sa.Column("wants_generation", sa.Boolean(), nullable=False),
        sa.Column("sections", sa.Text(), nullable=False),
        sa.Column("new_counts", sa.Text(), nullable=False),
        sa.Column("changes_at", sa.DateTime(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index(
        "ix_card_states_source_removed_done", "card_states", ["source_id", "removed", "is_done"],
    )
    op.create_index("ix_card_states_source_revision", "card_states", ["source_id", "revision"])
    op.create_index("ix_card_states_lemma", "card_states", ["lemma"])
    op.create_index("ix_card_states_word_id", "card_states", ["word_id"])
    op.create_index(
        "ix_card_states_changes_at", "card_states", ["changes_at"],
        sqlite_where=sa.text("changes_at IS NOT NULL"),
    )

    op.create_table(
        "word_states",
        sa.Column("word_id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("lemma", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
    )
    op.create_index("ix_word_states_source_id", "word_states", ["source_id"])
    op.create_index("ix_word_states_lemma", "word_states", ["lemma"])

    op.create_table(
        "phrase_words",
        sa.Column("lemma", sa.Text(), nullable=False),
        sa.Column("phrase_lemma", sa.Text(), nullable=False),
        sa.Column("phrase_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("zipf", sa.Float(), nullable=False),
        sa.Column("content", sa.Boolean(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("newness", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("phrase_id", "position"),
        sqlite_with_rowid=False,
    )
    op.create_index("ix_phrase_words_lemma", "phrase_words", ["lemma"])

    op.create_index(
        "ix_candidates_lower_lemma", "candidates", [sa.text("lower(lemma)"), "status"],
    )

    op.create_table(
        "projection_meta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint(f"id = {META_ID}", name="ck_projection_meta_one_row"),
    )
    op.execute(
        sa.text("INSERT INTO projection_meta (id, revision) VALUES (:id, :revision)")
        .bindparams(id=META_ID, revision=FIRST_REVISION),
    )


def downgrade() -> None:
    op.drop_index("ix_candidates_lower_lemma", table_name="candidates")
    op.drop_table("projection_meta")
    op.drop_table("phrase_words")
    op.drop_table("word_states")
    op.drop_table("card_states")
