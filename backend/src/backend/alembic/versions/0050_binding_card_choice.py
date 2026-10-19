"""The binding keeps the choice of its card.

Revision ID: 0050
Revises: 0049

A binding outlives its card when the source is deleted. Removing Known must still release
the binding of a card that was Known (the principle), while a Learn or Cloze card's binding
keeps the word Learning until its timer (Q13). The row now carries the card's choice: taken
from the card where it still exists, from the note kind for a row already orphaned (the
Learn or Cloze it was exported as). SQLite adds a column without NOT NULL only when it has
no default; every row is filled here and the app always writes it.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("anki_synced_cards", sa.Column("card_choice", sa.String(10), nullable=True))
    op.execute(
        "UPDATE anki_synced_cards SET card_choice = coalesce("
        "(SELECT p.choice FROM phrases p WHERE p.id = anki_synced_cards.phrase_id), note_kind)"
    )


def downgrade() -> None:
    op.drop_column("anki_synced_cards", "card_choice")
