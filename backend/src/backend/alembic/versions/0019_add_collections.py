"""Add collections table and sources.collection_id FK.

Revision ID: 0019
Revises: 0018
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    tables = sa.inspect(conn).get_table_names()

    if "collections" not in tables:
        op.create_table(
            "collections",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(200), nullable=False, unique=True),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    columns = [c["name"] for c in sa.inspect(conn).get_columns("sources")]
    if "collection_id" not in columns:
        with op.batch_alter_table("sources") as batch_op:
            batch_op.add_column(
                sa.Column("collection_id", sa.Integer, nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_sources_collection_id",
                "collections",
                ["collection_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch_op:
        batch_op.drop_constraint("fk_sources_collection_id", type_="foreignkey")
        batch_op.drop_column("collection_id")
    op.drop_table("collections")
