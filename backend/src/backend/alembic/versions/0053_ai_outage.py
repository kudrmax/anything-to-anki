"""The current outage of the AI, so the queue can say why AI work waits.

Revision ID: 0053
Revises: 0052

At most one row: the worker writes it when the AI answers no request and removes it
once the AI answers again.
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_outage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("since", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_outage")
