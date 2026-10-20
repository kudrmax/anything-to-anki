"""The chapter titles template becomes the default naming rule of any add of several sources.

Revision ID: 0052
Revises: 0051

`{{book_name}}` becomes `{{collection}}` and `{{chapter_title}}` becomes `{{title}}`.
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

OLD_KEY = "book_chapter_title_template"
NEW_KEY = "naming_rule"
RENAMED_PLACEHOLDERS: tuple[tuple[str, str], ...] = (
    ("{{book_name}}", "{{collection}}"),
    ("{{chapter_title}}", "{{title}}"),
)


def _move(from_key: str, to_key: str, *, forward: bool) -> None:
    bind = op.get_bind()
    row = bind.execute(
        text("SELECT value FROM settings WHERE key = :key"), {"key": from_key},
    ).first()
    if row is None:
        return
    value: str = row[0]
    for old, new in RENAMED_PLACEHOLDERS:
        value = value.replace(old, new) if forward else value.replace(new, old)
    bind.execute(text("DELETE FROM settings WHERE key = :key"), {"key": from_key})
    bind.execute(
        text("INSERT INTO settings (key, value) VALUES (:key, :value)"),
        {"key": to_key, "value": value},
    )


def upgrade() -> None:
    _move(OLD_KEY, NEW_KEY, forward=True)


def downgrade() -> None:
    _move(NEW_KEY, OLD_KEY, forward=False)
