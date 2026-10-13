"""Place a candidate's phrase and target in the source's document.

Revision ID: 0044
Revises: 0043

Each position is stored as JSON `[block, start_line, start_char, end_line, end_char]`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("phrase_position", sa.Text(), nullable=True))
        batch.add_column(sa.Column("target_position", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("target_position")
        batch.drop_column("phrase_position")
