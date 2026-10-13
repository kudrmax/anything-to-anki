"""Migration 0043 gives existing sources format, kind and role from their input method."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0042"
REVISION_UNDER_TEST = "0043"
NEW_COLUMNS = ("format", "kind", "role", "topic_query")

# input_method -> raw_text, expected (format, kind, role, topic_query)
CASES: dict[str, tuple[str, tuple[str | None, str | None, str, str | None]]] = {
    "text_pasted": ("prose", ("plain", "text", "content", None)),
    "lyrics_pasted": ("verse", ("plain", "song", "content", None)),
    "subtitles_file": ("srt", ("srt", "subtitles", "content", None)),
    "video_file": ("srt", ("video_file", "subtitles", "content", None)),
    "book_file": ("book", ("epub", "book", "content", None)),
    "markdown_file": ("# md", ("markdown", "text", "content", None)),
    "youtube_url": ("srt", ("youtube", "subtitles", "content", None)),
    "topic_query": ("job interviews", (None, None, "topic", "job interviews")),
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_existing_sources_get_format_kind_and_role(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    engine = create_engine(db_url)
    command.upgrade(cfg, REVISION_BEFORE)
    with engine.begin() as conn:
        for input_method, (raw_text, _) in CASES.items():
            conn.execute(
                text(
                    "INSERT INTO sources (raw_text, status, input_method, content_type,"
                    " created_at) VALUES (:raw_text, 'new', :input_method, 'text',"
                    " '2026-01-01 00:00:00')"
                ),
                {"raw_text": raw_text, "input_method": input_method},
            )

    command.upgrade(cfg, REVISION_UNDER_TEST)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT input_method, format, kind, role, topic_query FROM sources")
        ).all()
    found = {row[0]: tuple(row[1:]) for row in rows}
    assert found.pop("phrase_added") == (None, None, "saved_phrases", None)
    assert found == {method: expected for method, (_, expected) in CASES.items()}

    command.downgrade(cfg, REVISION_BEFORE)
    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(sources)"))}
    assert not columns & set(NEW_COLUMNS)
