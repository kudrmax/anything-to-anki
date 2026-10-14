"""Unknown words, and a card's phrase as one object: text, words, target.

Revision ID: 0048
Revises: 0047

A card kept its phrase four ways: the text (context_fragment, polished_fragment), the
target as written (surface_form), the target's place in the document (target_position)
and a mark that the phrase was an example (has_custom_context_fragment). Now the source
phrase and the rewritten one are each text + words by characters + target by word
numbers. fragment_unknown_count and
fragment_purity, counted once at processing, go: which words are new is decided on reading.

Applied to both copies of the app (prod and dev) on 2026-10-14: every card got its phrases
from its old text and target place. The carrying code was written for the data of that day
and is gone (it is in git history before this revision was emptied); the schema change
stays. A new database has no cards to carry.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

OLD_COLUMNS = (
    "fragment_unknown_count", "fragment_purity", "context_fragment", "surface_form",
    "has_custom_context_fragment", "polished_fragment", "target_position",
)


def upgrade() -> None:
    op.create_table(
        "unknown_words",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lemma", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("source_phrase", sa.Text(), nullable=False))
        batch.add_column(sa.Column("polished_phrase", sa.Text(), nullable=True))
        for column in OLD_COLUMNS:
            batch.drop_column(column)


def downgrade() -> None:
    raise NotImplementedError("The old phrase columns cannot be rebuilt from card phrases")
