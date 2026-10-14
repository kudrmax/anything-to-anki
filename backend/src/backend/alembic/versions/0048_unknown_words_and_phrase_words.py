"""Unknown words, and the words of a card's phrase instead of a count of new ones.

Revision ID: 0048
Revises: 0047

fragment_unknown_count and fragment_purity were counted once, when the source was
processed, and went stale as the user marked words or the phrase changed. A card
now keeps the words of its phrase; which of them are new is decided on reading.
Cards made before get their words when their source is first opened.
"""
import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unknown_words",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lemma", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("phrase_words", sa.Text(), nullable=True))
        batch.drop_column("fragment_unknown_count")
        batch.drop_column("fragment_purity")


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(
            sa.Column("fragment_purity", sa.String(10), nullable=False, server_default="clean"),
        )
        batch.add_column(
            sa.Column("fragment_unknown_count", sa.Integer(), nullable=False, server_default="0"),
        )
        batch.drop_column("phrase_words")
    op.drop_table("unknown_words")
