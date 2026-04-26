"""Add enrichment_cache table.

Revision ID: 0023
Revises: 0022
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrichment_cache",
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=False),
        sa.Column("context_fragment", sa.Text, nullable=False),
        # meaning
        sa.Column("meaning", sa.Text, nullable=True),
        sa.Column("translation", sa.Text, nullable=True),
        sa.Column("synonyms", sa.Text, nullable=True),
        sa.Column("examples", sa.Text, nullable=True),
        sa.Column("ipa", sa.String(100), nullable=True),
        sa.Column("meaning_generated_at", sa.DateTime, nullable=True),
        # media
        sa.Column("screenshot_path", sa.Text, nullable=True),
        sa.Column("audio_path", sa.Text, nullable=True),
        sa.Column("start_ms", sa.Integer, nullable=True),
        sa.Column("end_ms", sa.Integer, nullable=True),
        sa.Column("media_generated_at", sa.DateTime, nullable=True),
        # pronunciation
        sa.Column("us_audio_path", sa.Text, nullable=True),
        sa.Column("uk_audio_path", sa.Text, nullable=True),
        sa.Column("pronunciation_generated_at", sa.DateTime, nullable=True),
        # tts
        sa.Column("tts_audio_path", sa.Text, nullable=True),
        sa.Column("tts_generated_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("source_id", "lemma", "pos", "context_fragment"),
    )


def downgrade() -> None:
    op.drop_table("enrichment_cache")
