"""Create the built-in "Saved phrases" source.

Revision ID: 0039
Revises: 0038

It keeps phrases met anywhere and added one by one by hand, so it has no
text of its own and is never processed. Creating it here makes it show in
the list before the first phrase is added.
"""
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None

PHRASES_CONTENT_TYPE = "phrases"


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        sa.text("SELECT 1 FROM sources WHERE content_type = :content_type"),
        {"content_type": PHRASES_CONTENT_TYPE},
    ).first()
    if exists:
        return
    sources = sa.table(
        "sources",
        sa.column("raw_text", sa.Text),
        sa.column("title", sa.String),
        sa.column("status", sa.String),
        sa.column("input_method", sa.String),
        sa.column("content_type", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    op.bulk_insert(sources, [{
        "raw_text": "",
        "title": "Saved phrases",
        "status": "done",
        "input_method": "phrase_added",
        "content_type": PHRASES_CONTENT_TYPE,
        "created_at": datetime.now(tz=UTC).replace(tzinfo=None),
    }])


def downgrade() -> None:
    op.execute(
        "DELETE FROM candidates WHERE source_id IN "
        f"(SELECT id FROM sources WHERE content_type = '{PHRASES_CONTENT_TYPE}')"
    )
    op.execute(f"DELETE FROM sources WHERE content_type = '{PHRASES_CONTENT_TYPE}'")
