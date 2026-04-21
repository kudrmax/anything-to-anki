"""Add cefr_breakdowns table.

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"


def upgrade() -> None:
    op.create_table(
        "cefr_breakdowns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("decision_method", sa.String(10), nullable=False),
        sa.Column("cambridge", sa.String(10), nullable=True),
        sa.Column("cefrpy", sa.String(10), nullable=True),
        sa.Column("efllex_distribution", sa.Text(), nullable=True),
        sa.Column("oxford", sa.String(10), nullable=True),
        sa.Column("kelly", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cefr_breakdowns")
