"""`recent_uses`: the last moment the user worked with each source and collection, the
order of Recent.

Filled from what is known: a source outside collections was used when added and when a
card of it was last marked; a collection, at the latest of the same moments over the
sources right in it. Sources inside a collection get no row: their collection stands for
them.

Revision ID: 0072
Revises: 0071
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None

_SOURCE_MOMENTS = """
    SELECT s.id AS source_id, s.collection_id AS collection_id, s.created_at AS used_at
    FROM sources s
    UNION ALL
    SELECT c.source_id, s.collection_id, c.studied_at
    FROM candidates c JOIN sources s ON s.id = c.source_id
    WHERE c.studied_at IS NOT NULL
"""


def upgrade() -> None:
    op.create_table(
        "recent_uses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id", sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=True, unique=True,
        ),
        sa.Column(
            "collection_id", sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=True, unique=True,
        ),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(source_id IS NULL) != (collection_id IS NULL)", name="ck_recent_uses_one_item",
        ),
    )
    op.execute(f"""
        INSERT INTO recent_uses (source_id, used_at)
        SELECT source_id, MAX(used_at) FROM ({_SOURCE_MOMENTS})
        WHERE collection_id IS NULL
        GROUP BY source_id
    """)
    op.execute(f"""
        INSERT INTO recent_uses (collection_id, used_at)
        SELECT collection_id, MAX(used_at) FROM ({_SOURCE_MOMENTS})
        WHERE collection_id IN (SELECT id FROM collections WHERE deleted_at IS NULL)
        GROUP BY collection_id
    """)


def downgrade() -> None:
    op.drop_table("recent_uses")
