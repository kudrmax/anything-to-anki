"""Drop what sources were before documents.

Revision ID: 0046
Revises: 0045

raw_text, cleaned_text, input_method and content_type gave way to the document,
format, kind and role (0042-0045). A downgrade brings the columns back empty:
what they held is in the documents now.
"""
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("raw_text")
        batch.drop_column("cleaned_text")
        batch.drop_column("input_method")
        batch.drop_column("content_type")


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("raw_text", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("cleaned_text", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("input_method", sa.String(20), nullable=False, server_default="text_pasted"),
        )
        batch.add_column(
            sa.Column("content_type", sa.String(10), nullable=False, server_default="text"),
        )
