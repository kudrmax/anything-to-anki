"""`collections.favorited_at`: when the collection was added to favorites, which list them
in that order; NULL while it is not a favorite.

Revision ID: 0062
Revises: 0060
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collections", sa.Column("favorited_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("collections", "favorited_at")
