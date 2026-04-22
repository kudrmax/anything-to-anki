"""Drop cefr_level column from candidates table.

CEFR level is now computed at runtime from cefr_breakdowns votes.
Before running this migration, ensure all candidates have a
cefr_breakdowns row (run: make backfill-breakdowns).

Revision ID: 0017
Revises: 0016
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety check: abort if any candidate is missing a breakdown row
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM candidates c "
            "LEFT JOIN cefr_breakdowns b ON b.candidate_id = c.id "
            "WHERE b.id IS NULL"
        ),
    )
    count = result.scalar()
    if count:
        raise RuntimeError(
            f"{count} candidates have no cefr_breakdowns row. "
            "Run 'make backfill-breakdowns' first."
        )

    with op.batch_alter_table("candidates") as batch_op:
        batch_op.drop_column("cefr_level")


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch_op:
        batch_op.add_column(
            sa.Column("cefr_level", sa.String(10), nullable=False, server_default=""),
        )
