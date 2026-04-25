"""Make known_words.pos nullable, add partial unique index for wildcard entries.

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, use batch mode
    with op.batch_alter_table("known_words") as batch_op:
        batch_op.alter_column("pos", existing_type=sa.String(10), nullable=True)

    # Partial unique index: one wildcard per lemma
    op.execute(
        "CREATE UNIQUE INDEX uq_known_word_lemma_wildcard "
        "ON known_words(lemma) WHERE pos IS NULL"
    )


def downgrade() -> None:
    op.drop_index("uq_known_word_lemma_wildcard", table_name="known_words")

    with op.batch_alter_table("known_words") as batch_op:
        batch_op.alter_column("pos", existing_type=sa.String(10), nullable=False)
