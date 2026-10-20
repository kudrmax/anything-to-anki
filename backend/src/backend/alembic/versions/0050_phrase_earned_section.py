"""A phrase stores the section it earned.

Revision ID: 0050
Revises: 0049

The column stays empty on existing phrases: `make fix-sections` stamps them.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None

SECTION_LENGTH = 20


def upgrade() -> None:
    with op.batch_alter_table("phrases") as batch:
        batch.add_column(sa.Column("earned_section", sa.String(SECTION_LENGTH), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("phrases") as batch:
        batch.drop_column("earned_section")
