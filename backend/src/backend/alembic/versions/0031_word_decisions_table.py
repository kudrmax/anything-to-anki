"""Add word_decisions table.

Revision ID: 0031
Revises: 0030

The user's latest verdict on a word — known or to learn — with the word's
frequency. It calibrates the frequent word threshold and must survive
deleting the source the word came from, so it does not live in candidates.
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "word_decisions",
        sa.Column("lemma", sa.String(100), primary_key=True),
        sa.Column("zipf_frequency", sa.Float, nullable=False),
        sa.Column("is_known", sa.Boolean, nullable=False),
        sa.Column("decided_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("word_decisions")
