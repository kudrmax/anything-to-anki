"""The current outage of the AI, so every screen can say why AI answers nothing.

Revision ID: 0053
Revises: 0052

At most one row: any AI call that finds the AI unavailable writes it, any call the AI
answers removes it. `vpn_required` marks a blocked country.
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
        sa.Column("vpn_required", sa.Boolean, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_outage")
