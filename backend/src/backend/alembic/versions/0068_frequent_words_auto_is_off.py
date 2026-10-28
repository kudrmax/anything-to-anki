"""The Auto option of the frequent word threshold is gone: a saved Auto becomes Off.

Revision ID: 0068
Revises: 0066

Downgrade leaves Off as it is: an Off saved before this revision can't be told apart.
"""
from __future__ import annotations

from alembic import op

revision = "0068"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE settings SET value = 'off' "
        "WHERE key = 'frequent_word_threshold' AND value = 'auto'",
    )


def downgrade() -> None:
    pass
