"""Add phrase origin to candidates.

Revision ID: 0028
Revises: 0027

Candidates of a topic source borrow their phrase from another source or get
a generated one. origin_kind is 'source' or 'generated', origin_title is the
title of the source the phrase came from. Both stay NULL for regular
candidates, whose phrase comes from their own source.
"""
import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("origin_kind", sa.String(10), nullable=True))
    op.add_column("candidates", sa.Column("origin_title", sa.String(200), nullable=True))


def downgrade() -> None:
    # SQLite drops columns by rebuilding the table; keep AUTOINCREMENT so
    # candidate ids are still never reused (see 0025).
    with op.batch_alter_table(
        "candidates", table_kwargs={"sqlite_autoincrement": True},
    ) as batch:
        batch.drop_column("origin_title")
        batch.drop_column("origin_kind")
