"""Say how a source was laid out, what it is, and what role it plays.

Revision ID: 0043
Revises: 0042

format, kind and role take over from input_method and content_type. A topic's
query moves to topic_query. Existing sources get them from their input method.
"""
import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

# input_method -> (format, kind, role)
_BY_INPUT_METHOD: dict[str, tuple[str | None, str | None, str]] = {
    "text_pasted": ("plain", "text", "content"),
    "lyrics_pasted": ("plain", "song", "content"),
    "subtitles_file": ("srt", "subtitles", "content"),
    "video_file": ("video_file", "subtitles", "content"),
    "book_file": ("epub", "book", "content"),
    "markdown_file": ("markdown", "text", "content"),
    "youtube_url": ("youtube", "subtitles", "content"),
    "topic_query": (None, None, "topic"),
    "phrase_added": (None, None, "saved_phrases"),
}


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("format", sa.String(20), nullable=True))
        batch.add_column(sa.Column("kind", sa.String(20), nullable=True))
        batch.add_column(
            sa.Column("role", sa.String(20), nullable=False, server_default="content")
        )
        batch.add_column(sa.Column("topic_query", sa.Text(), nullable=True))

    connection = op.get_bind()
    for input_method, (source_format, kind, role) in _BY_INPUT_METHOD.items():
        connection.execute(
            sa.text(
                "UPDATE sources SET format = :format, kind = :kind, role = :role"
                " WHERE input_method = :input_method"
            ),
            {"format": source_format, "kind": kind, "role": role, "input_method": input_method},
        )
    connection.execute(
        sa.text("UPDATE sources SET topic_query = raw_text WHERE input_method = 'topic_query'")
    )


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("topic_query")
        batch.drop_column("role")
        batch.drop_column("kind")
        batch.drop_column("format")
