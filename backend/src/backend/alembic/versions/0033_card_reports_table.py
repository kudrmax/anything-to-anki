"""Add card_reports table.

Revision ID: 0033
Revises: 0032

The user's complaints about cards ("phrase too long", "wrong boundary"),
with a snapshot of the card, to analyse selection quality later. No foreign
keys: a report outlives the candidate and the source.
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("source_title", sa.String(200), nullable=False),
        sa.Column("candidate_id", sa.Integer, nullable=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("surface_form", sa.String(100), nullable=True),
        sa.Column("context_fragment", sa.Text, nullable=False),
        sa.Column("zipf_frequency", sa.Float, nullable=False),
        sa.Column("cefr_level", sa.String(10), nullable=True),
        sa.Column("fragment_unknown_count", sa.Integer, nullable=False),
        sa.Column("is_phrasal_verb", sa.Boolean, nullable=False),
        sa.Column("comment", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("card_reports")
