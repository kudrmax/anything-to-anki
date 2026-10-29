"""`phrases.removed_by_user`: the user removed the card of the phrase; it is never shown
again and a rebuild keeps it, so the analysis does not make it anew. False on existing
phrases.

Revision ID: 0071
Revises: 0070
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("phrases") as batch:
        batch.add_column(sa.Column(
            "removed_by_user", sa.Boolean(), nullable=False, server_default="0",
        ))


def downgrade() -> None:
    with op.batch_alter_table("phrases") as batch:
        batch.drop_column("removed_by_user")
