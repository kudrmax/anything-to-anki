"""Store the document of a source.

Revision ID: 0042
Revises: 0041

The document is the text of a source as the application works with it: blocks
of headings, paragraphs and list items, stored as JSON, one row per source.
"""
import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("document", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("source_documents")
