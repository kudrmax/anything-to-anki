"""Add bootstrap calibration tables.

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bootstrap_index_meta",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="none"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("built_at", sa.DateTime, nullable=True),
        sa.Column("word_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.execute("INSERT INTO bootstrap_index_meta (id, status, word_count) VALUES (1, 'none', 0)")

    op.create_table(
        "bootstrap_word_cell",
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("zipf_value", sa.Float, nullable=False),
        sa.PrimaryKeyConstraint("lemma", "cefr_level"),
    )


def downgrade() -> None:
    op.drop_table("bootstrap_word_cell")
    op.drop_table("bootstrap_index_meta")
