"""Let a candidate keep an AI-polished, easier version of its phrase.

Revision ID: 0037
Revises: 0036

`context_fragment` stays the phrase from the source. `polished_fragment` is
what AI rewrote it into; `polish_reverted` means the user went back to the
source phrase.
"""
import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("polished_fragment", sa.Text, nullable=True))
    op.add_column(
        "candidates",
        sa.Column("polish_reverted", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.drop_column("polish_reverted")
        batch.drop_column("polished_fragment")
