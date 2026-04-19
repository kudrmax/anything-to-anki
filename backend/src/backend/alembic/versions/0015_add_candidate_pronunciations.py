"""Add candidate_pronunciations table.

Revision ID: 0015
Revises: 0014
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_pronunciations",
        sa.Column("candidate_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("us_audio_path", sa.Text(), nullable=True),
        sa.Column("uk_audio_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="done"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("candidate_pronunciations")
