"""Add fragment_unknown_count to candidates.

Revision ID: 0029
Revises: 0028

How many words of the phrase besides the target the user probably does not
know. Candidates with fewer unknown words go higher in the list.
"""
import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("fragment_unknown_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # SQLite drops columns by rebuilding the table; keep AUTOINCREMENT so
    # candidate ids are still never reused (see 0025).
    with op.batch_alter_table(
        "candidates", table_kwargs={"sqlite_autoincrement": True},
    ) as batch:
        batch.drop_column("fragment_unknown_count")
