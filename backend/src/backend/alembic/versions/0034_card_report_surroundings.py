"""Add the source text around the phrase to card_reports.

Revision ID: 0034
Revises: 0033

To judge "wrong phrase boundary" one needs what the boundary cut off. Both
columns stay NULL when the phrase is not in the source text.
"""
import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("card_reports", sa.Column("text_before", sa.Text, nullable=True))
    op.add_column("card_reports", sa.Column("text_after", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("card_reports") as batch:
        batch.drop_column("text_after")
        batch.drop_column("text_before")
