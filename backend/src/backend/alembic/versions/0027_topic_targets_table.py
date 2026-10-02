"""Add topic_targets table.

Revision ID: 0027
Revises: 0026

A topic source has no text of its own: AI turns its request into targets,
which are kept here so that processing (and reprocessing) can collect
phrases for them without calling AI again.
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_targets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey(
                "sources.id",
                ondelete="CASCADE",
                name="fk_topic_targets_source_id_sources",
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("phrase", sa.String(100), nullable=False),
        sa.Column("example", sa.Text, nullable=False),
    )
    op.create_index("ix_topic_targets_source_id", "topic_targets", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_topic_targets_source_id", table_name="topic_targets")
    op.drop_table("topic_targets")
