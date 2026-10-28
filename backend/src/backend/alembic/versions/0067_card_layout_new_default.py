"""The review card has a new default layout. Every user moves to it: a saved layout is
dropped, so the card is laid out by the default until the user changes it again.

Revision ID: 0067
Revises: 0066
"""
from __future__ import annotations

from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'card_layout'")


def downgrade() -> None:
    # The dropped layouts are gone; without a saved one the card uses the default.
    pass
