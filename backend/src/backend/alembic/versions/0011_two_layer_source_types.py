"""Replace source_type with input_method + content_type, add source_url.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0011"
down_revision = "0010"

_SOURCE_TYPE_TO_INPUT_METHOD = {
    "text": "text_pasted",
    "lyrics": "lyrics_pasted",
    "subtitles": "subtitles_file",
    "video": "video_file",
}

_INPUT_METHOD_TO_CONTENT_TYPE = {
    "text_pasted": "text",
    "lyrics_pasted": "lyrics",
    "subtitles_file": "text",
    "video_file": "video",
    "youtube_url": "video",
}


def _column_exists(conn: sa.engine.Connection, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Rename source_type → input_method (idempotent: skip if already renamed)
    if _column_exists(conn, "sources", "source_type"):
        conn.execute(text("ALTER TABLE sources RENAME COLUMN source_type TO input_method"))

    # 2. Migrate data: old input_method values → new values
    for old_val, new_val in _SOURCE_TYPE_TO_INPUT_METHOD.items():
        conn.execute(
            text("UPDATE sources SET input_method = :new WHERE input_method = :old"),
            {"new": new_val, "old": old_val},
        )

    # 3. Add content_type column if not present
    if not _column_exists(conn, "sources", "content_type"):
        op.add_column("sources", sa.Column("content_type", sa.String(10), nullable=True))

    # 4. Backfill content_type based on input_method
    for im_val, ct_val in _INPUT_METHOD_TO_CONTENT_TYPE.items():
        conn.execute(
            text("UPDATE sources SET content_type = :ct WHERE input_method = :im AND content_type IS NULL"),
            {"ct": ct_val, "im": im_val},
        )

    # Default for any unmatched rows
    conn.execute(
        text("UPDATE sources SET content_type = 'text' WHERE content_type IS NULL")
    )

    # 5. Make content_type NOT NULL via batch (SQLite requires table rebuild)
    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column(
            "content_type",
            existing_type=sa.String(10),
            nullable=False,
        )

    # 6. Add source_url column if not present
    if not _column_exists(conn, "sources", "source_url"):
        op.add_column("sources", sa.Column("source_url", sa.Text, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    if _column_exists(conn, "sources", "source_url"):
        op.drop_column("sources", "source_url")
    if _column_exists(conn, "sources", "content_type"):
        op.drop_column("sources", "content_type")

    reverse_map = {v: k for k, v in _SOURCE_TYPE_TO_INPUT_METHOD.items()}
    for new_val, old_val in reverse_map.items():
        conn.execute(
            text("UPDATE sources SET input_method = :old WHERE input_method = :new"),
            {"old": old_val, "new": new_val},
        )

    if _column_exists(conn, "sources", "input_method"):
        conn.execute(text("ALTER TABLE sources RENAME COLUMN input_method TO source_type"))
