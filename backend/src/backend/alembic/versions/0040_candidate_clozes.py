"""Add candidate_clozes table.

Revision ID: 0040
Revises: 0039
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_clozes",
        sa.Column(
            "candidate_id",
            sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("hidden_word_indices", sa.Text(), nullable=False),
        sa.Column("hint_kind", sa.String(20), nullable=False),
        sa.Column("custom_hint", sa.Text(), nullable=True),
        sa.Column("phrase", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candidate_clozes")
