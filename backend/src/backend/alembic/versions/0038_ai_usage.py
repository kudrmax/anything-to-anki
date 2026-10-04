"""Keep a history of AI calls and the tokens they consumed.

Revision ID: 0038
Revises: 0037

Before this, token usage only reached the ai_proxy log.
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("feature", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False),
        sa.Column("cache_creation_tokens", sa.Integer, nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("succeeded", sa.Boolean, nullable=False),
    )
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_table("ai_usage")
