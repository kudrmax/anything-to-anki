"""Migration 0072 fills Recent from what is known: a source outside collections by its
adding and its last marked card, a collection by the same moments of the sources right in
it."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0071"
REVISION_UNDER_TEST = "0072"
BOOK, EMPTY, GONE = 11, 12, 13
LOOSE, MARKED, CHAPTER_1, CHAPTER_2, IN_GONE = 11, 12, 13, 14, 15


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _day(day: int) -> str:
    return f"2026-01-{day:02d} 00:00:00.000000"


@pytest.fixture
def url(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(db_url), REVISION_BEFORE)
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            for collection_id, name, deleted in ((BOOK, "Book", None), (EMPTY, "Empty", None),
                                                 (GONE, "Gone", _day(9))):
                conn.execute(text(
                    "INSERT INTO collections (id, name, position, created_at, deleted_at) "
                    "VALUES (:id, :name, 0, :created, :deleted)",
                ), {"id": collection_id, "name": name, "created": _day(1), "deleted": deleted})
            for source_id, collection_id, added in (
                (LOOSE, None, 2), (MARKED, None, 3), (CHAPTER_1, BOOK, 4), (CHAPTER_2, BOOK, 4),
                (IN_GONE, GONE, 5),
            ):
                conn.execute(text(
                    "INSERT INTO sources (id, title, status, created_at, role, collection_id) "
                    "VALUES (:id, 't', 'done', :added, 'content', :collection)",
                ), {"id": source_id, "added": _day(added), "collection": collection_id})
            for source_id, studied in ((MARKED, 8), (MARKED, 6), (CHAPTER_2, 7)):
                conn.execute(text(
                    "INSERT INTO candidates (source_id, lemma, pos, zipf_frequency, "
                    "is_sweet_spot, occurrences, is_phrasal_verb, studied_at) "
                    "VALUES (:source, :lemma, 'NOUN', 3.0, 0, 1, 0, :studied)",
                ), {
                    "source": source_id,
                    "lemma": f"w{source_id}{studied}",
                    "studied": _day(studied),
                })
    finally:
        engine.dispose()
    return db_url


def _uses(url: str) -> set[tuple[int | None, int | None, str]]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT source_id, collection_id, used_at FROM recent_uses"))
            return {(row[0], row[1], row[2]) for row in rows}
    finally:
        engine.dispose()


def test_sources_and_collections_are_used_at_their_latest_moment(url: str) -> None:
    command.upgrade(_alembic_config(url), REVISION_UNDER_TEST)

    seeded = {LOOSE, MARKED, CHAPTER_1, CHAPTER_2, IN_GONE, BOOK, EMPTY, GONE}
    # The saved phrases source an earlier migration made is used like any other source.
    assert {use for use in _uses(url) if (use[0] or use[1]) in seeded} == {
        (LOOSE, None, _day(2)),
        (MARKED, None, _day(8)),
        (None, BOOK, _day(7)),
    }
