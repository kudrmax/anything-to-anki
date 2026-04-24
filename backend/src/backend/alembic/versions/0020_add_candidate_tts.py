"""Add candidate_tts table.

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_tts",
        sa.Column("candidate_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("audio_path", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("candidate_tts")
