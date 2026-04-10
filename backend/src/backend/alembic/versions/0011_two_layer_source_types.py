"""Replace source_type with input_method + content_type, add source_url.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

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


def upgrade() -> None:
    # 1. Rename source_type → input_method
    op.alter_column("sources", "source_type", new_column_name="input_method")

    # 2. Migrate data: old values → new values
    sources = sa.table("sources", sa.column("input_method", sa.String))
    for old_val, new_val in _SOURCE_TYPE_TO_INPUT_METHOD.items():
        op.execute(
            sources.update()
            .where(sources.c.input_method == old_val)
            .values(input_method=new_val)
        )

    # 3. Add content_type column (nullable first, then backfill, then not-null)
    op.add_column("sources", sa.Column("content_type", sa.String(10), nullable=True))

    for im_val, ct_val in _INPUT_METHOD_TO_CONTENT_TYPE.items():
        op.execute(
            sources.update()
            .where(sources.c.input_method == im_val)
            .values(content_type=ct_val)
        )

    # For any rows that didn't match, default to "text"
    ct_col = sa.table("sources", sa.column("content_type", sa.String))
    op.execute(
        ct_col.update()
        .where(ct_col.c.content_type.is_(None))
        .values(content_type="text")
    )

    with op.batch_alter_table("sources") as batch_op:
        batch_op.alter_column("content_type", nullable=False)

    # 4. Add source_url column
    op.add_column("sources", sa.Column("source_url", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("sources", "source_url")
    op.drop_column("sources", "content_type")

    sources = sa.table("sources", sa.column("input_method", sa.String))
    reverse_map = {v: k for k, v in _SOURCE_TYPE_TO_INPUT_METHOD.items()}
    for new_val, old_val in reverse_map.items():
        op.execute(
            sources.update()
            .where(sources.c.input_method == new_val)
            .values(input_method=old_val)
        )

    op.alter_column("sources", "input_method", new_column_name="source_type")
