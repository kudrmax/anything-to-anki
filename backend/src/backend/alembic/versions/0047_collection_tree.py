"""Collections become a two-level tree with manual order and soft delete.

Revision ID: 0047
Revises: 0046

A name is unique among live siblings now, not globally. The downgrade fails if
two collections under different parents share a name: the old schema can't hold that.
"""
import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

_SIBLING_NAME_INDEX = "uq_collections_sibling_name"
_NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("collections", naming_convention=_NAMING) as batch:
        batch.drop_constraint("uq_collections_name", type_="unique")
        batch.add_column(sa.Column("parent_id", sa.Integer, nullable=True))
        batch.add_column(sa.Column("position", sa.Integer, nullable=False, server_default="0"))
        batch.add_column(sa.Column("deleted_at", sa.DateTime, nullable=True))
        batch.create_foreign_key(
            "fk_collections_parent_id", "collections", ["parent_id"], ["id"], ondelete="CASCADE",
        )

    conn = op.get_bind()
    ids = conn.execute(sa.text("SELECT id FROM collections ORDER BY lower(name), id")).scalars()
    for position, collection_id in enumerate(list(ids)):
        conn.execute(
            sa.text("UPDATE collections SET position = :position WHERE id = :id"),
            {"position": position, "id": collection_id},
        )

    op.create_index(
        _SIBLING_NAME_INDEX,
        "collections",
        [sa.text("coalesce(parent_id, 0)"), "name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "collection_evictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "collection_id", sa.Integer,
            sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column(
            "source_id", sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("previous_collection_id", sa.Integer, nullable=False),
        sa.Column("moved_to_collection_id", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("collection_evictions")
    op.drop_index(_SIBLING_NAME_INDEX, table_name="collections")
    with op.batch_alter_table("collections", naming_convention=_NAMING) as batch:
        batch.drop_constraint("fk_collections_parent_id", type_="foreignkey")
        batch.drop_column("deleted_at")
        batch.drop_column("position")
        batch.drop_column("parent_id")
        batch.create_unique_constraint("uq_collections_name", ["name"])
