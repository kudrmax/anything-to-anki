"""Migration 0041 moves picked pictures out of the video frame slot."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0040"
REVISION_UNDER_TEST = "0041"
SOURCE_ID = 2
FRAME_CANDIDATE_ID = 1
PICKED_CANDIDATE_ID = 2
FRAME_PATH = f"/data/media/{SOURCE_ID}/{FRAME_CANDIDATE_ID}_screenshot.webp"
PICKED_PATH = f"/data/media/{SOURCE_ID}/{PICKED_CANDIDATE_ID}_screenshot.0a1b2c3d4e.webp"
AUDIO_PATH = f"/data/media/{SOURCE_ID}/{PICKED_CANDIDATE_ID}_audio.m4a"


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _insert_candidate(conn: Connection, candidate_id: int) -> None:
    conn.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
            " is_sweet_spot, context_fragment, fragment_purity, occurrences, status,"
            " is_phrasal_verb, has_custom_context_fragment)"
            " VALUES (:id, :source_id, :lemma, 'NOUN', 4.0, 0, 'ctx', 'clean', 1,"
            " 'pending', 0, 0)"
        ),
        {"id": candidate_id, "source_id": SOURCE_ID, "lemma": f"word{candidate_id}"},
    )


def _insert_cache(conn: Connection, lemma: str, screenshot_path: str) -> None:
    conn.execute(
        text(
            "INSERT INTO enrichment_cache (source_id, lemma, pos, context_fragment,"
            " screenshot_path) VALUES (:source_id, :lemma, 'NOUN', 'ctx', :path)"
        ),
        {"source_id": SOURCE_ID, "lemma": lemma, "path": screenshot_path},
    )


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    command.upgrade(_alembic_config(url), REVISION_BEFORE)
    with create_engine(url).begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sources (id, raw_text, title, status, input_method,"
                " content_type, created_at)"
                " VALUES (:id, 'text', 'title', 'done', 'video_file', 'video',"
                " '2026-01-01 00:00:00')"
            ),
            {"id": SOURCE_ID},
        )
        _insert_candidate(conn, FRAME_CANDIDATE_ID)
        _insert_candidate(conn, PICKED_CANDIDATE_ID)
        conn.execute(
            text(
                "INSERT INTO candidate_media (candidate_id, screenshot_path, audio_path,"
                " start_ms, end_ms) VALUES (:cid, :shot, :audio, 1000, 2000)"
            ),
            [
                {"cid": FRAME_CANDIDATE_ID, "shot": FRAME_PATH, "audio": None},
                {"cid": PICKED_CANDIDATE_ID, "shot": PICKED_PATH, "audio": AUDIO_PATH},
            ],
        )
        _insert_cache(conn, "frame", FRAME_PATH)
        _insert_cache(conn, "picked", PICKED_PATH)
    return url


def _rows(url: str, sql: str) -> list[tuple[object, ...]]:
    with create_engine(url).connect() as conn:
        return [tuple(row) for row in conn.execute(text(sql))]


def test_upgrade_moves_picked_pictures_and_keeps_frames(db_url: str) -> None:
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)

    assert _rows(db_url, "SELECT candidate_id, image_path FROM candidate_meaning_images") == [
        (PICKED_CANDIDATE_ID, PICKED_PATH),
    ]
    assert _rows(
        db_url,
        "SELECT candidate_id, screenshot_path, audio_path, start_ms FROM candidate_media"
        " ORDER BY candidate_id",
    ) == [
        (FRAME_CANDIDATE_ID, FRAME_PATH, None, 1000),
        (PICKED_CANDIDATE_ID, None, AUDIO_PATH, 1000),
    ]
    assert _rows(
        db_url,
        "SELECT lemma, screenshot_path, meaning_image_path FROM enrichment_cache ORDER BY lemma",
    ) == [
        ("frame", FRAME_PATH, None),
        ("picked", None, PICKED_PATH),
    ]


def test_meaning_image_follows_its_candidate(db_url: str) -> None:
    command.upgrade(_alembic_config(db_url), REVISION_UNDER_TEST)

    foreign_keys = inspect(create_engine(db_url)).get_foreign_keys("candidate_meaning_images")
    assert [(fk["referred_table"], fk["options"].get("ondelete")) for fk in foreign_keys] == [
        ("candidates", "CASCADE"),
    ]


def test_downgrade_puts_picked_pictures_back(db_url: str) -> None:
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_UNDER_TEST)
    command.downgrade(cfg, REVISION_BEFORE)

    assert "candidate_meaning_images" not in inspect(create_engine(db_url)).get_table_names()
    assert _rows(
        db_url, "SELECT candidate_id, screenshot_path FROM candidate_media ORDER BY candidate_id",
    ) == [
        (FRAME_CANDIDATE_ID, FRAME_PATH),
        (PICKED_CANDIDATE_ID, PICKED_PATH),
    ]
    assert _rows(
        db_url, "SELECT lemma, screenshot_path FROM enrichment_cache ORDER BY lemma",
    ) == [
        ("frame", FRAME_PATH),
        ("picked", PICKED_PATH),
    ]
