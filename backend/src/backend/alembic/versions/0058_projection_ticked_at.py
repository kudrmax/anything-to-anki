"""`projection_meta.ticked_at`: the moment the projection was last brought up to date with
time, by the full rebuild or the worker's time tick (spec §5). The tick recomputes the
lemmas whose Anki timer came due since then, the ones no card row carries too.

Revision ID: 0058
Revises: 0057
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projection_meta", sa.Column("ticked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("projection_meta", "ticked_at")
