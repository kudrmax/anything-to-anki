"""`calibration_skipped_word`: words calibration showed and the user did not tap, so it does
not ask them again. Starts empty.

Revision ID: 0070
Revises: 0069
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calibration_skipped_word",
        sa.Column("lemma", sa.String(100), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("calibration_skipped_word")
