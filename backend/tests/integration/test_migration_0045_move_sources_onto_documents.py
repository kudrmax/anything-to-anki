"""Migration 0045 moves sources made before documents onto documents, keeping what is seen."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import Connection, create_engine, text

pytestmark = pytest.mark.integration

SRT = (
    "1\n00:00:01,000 --> 00:00:02,000\nGrappling hook!\n\n"
    "2\n00:00:03,000 --> 00:00:05,000\nAnd I will have\na grappling hook!\n\n"
    "3\n00:00:06,000 --> 00:00:07,000\nGrappling hook!"
)
VIDEO_CLEANED = "Grappling hook!\nAnd I will have\na grappling hook!\nGrappling hook!"


def _config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _source(
    conn: Connection, sid: int, fmt: str, kind: str, raw: str, cleaned: str | None,
) -> None:
    conn.execute(text(
        "INSERT INTO sources (id, raw_text, cleaned_text, status, input_method, content_type,"
        " created_at, format, kind, role) VALUES (:id, :raw, :cleaned, 'done', 'text_pasted',"
        " 'text', '2026-01-01 00:00:00', :fmt, :kind, 'content')"
    ), {"id": sid, "raw": raw, "cleaned": cleaned, "fmt": fmt, "kind": kind})


def _candidate(
    conn: Connection, cid: int, sid: int, lemma: str, fragment: str,
    surface: str | None = None, custom: bool = False, time: tuple[int, int] | None = None,
) -> None:
    conn.execute(text(
        "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
        " context_fragment, fragment_purity, occurrences, status, surface_form, is_phrasal_verb,"
        " has_custom_context_fragment) VALUES (:id, :sid, :lemma, 'NOUN', 3.0, 1, :fragment,"
        " 'clean', 1, 'pending', :surface, :phrasal, :custom)"
    ), {
        "id": cid, "sid": sid, "lemma": lemma, "fragment": fragment, "surface": surface,
        "phrasal": " " in lemma, "custom": custom,
    })
    if time:
        conn.execute(text(
            "INSERT INTO candidate_media (candidate_id, start_ms, end_ms) VALUES (:id, :s, :e)"
        ), {"id": cid, "s": time[0], "e": time[1]})


def _positions(conn: Connection, cid: int) -> tuple[list[int] | None, list[int] | None]:
    phrase, target = conn.execute(
        text("SELECT phrase_position, target_position FROM candidates WHERE id = :id"),
        {"id": cid},
    ).one()
    return (json.loads(phrase) if phrase else None, json.loads(target) if target else None)


def test_old_sources_get_documents_and_places(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _config(db_url)
    command.upgrade(cfg, "0044")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        cleaned = "First line\nsecond line.\n\nTake it on, she said."
        _source(conn, 101, "plain", "text", "raw", cleaned)
        _candidate(conn, 10, 101, "second", "line second line")
        _candidate(conn, 11, 101, "take on", "Take it on", surface="Take it on")
        _candidate(conn, 12, 101, "example", "An example made up.", custom=True)
        _source(conn, 102, "video_file", "subtitles", SRT, VIDEO_CLEANED)
        _candidate(
            conn, 20, 102, "grapple", "Grappling hook!", surface="Grappling", time=(6000, 7000),
        )
        _source(conn, 103, "epub", "book", "Chapter one.\n\nIt went on.", None)
    command.upgrade(cfg, "0045")

    with engine.connect() as conn:
        documents = {
            sid: json.loads(doc)
            for sid, doc in conn.execute(text("SELECT source_id, document FROM source_documents"))
        }
        assert documents[101] == {"blocks": [
            {"type": "paragraph", "mode": "flow",
             "lines": [{"text": "First line"}, {"text": "second line."}]},
            {"type": "paragraph", "mode": "flow", "lines": [{"text": "Take it on, she said."}]},
        ]}
        assert _positions(conn, 10) == ([0, 0, 6, 1, 11], [0, 1, 0, 1, 6])
        assert _positions(conn, 11) == ([1, 0, 0, 0, 10], [1, 0, 0, 0, 10])
        assert _positions(conn, 12) == (None, None)

        assert [line.get("start_ms") for line in documents[102]["blocks"][0]["lines"]] == [
            1000, 3000, 3000, 6000,
        ]
        # The clip was cut from the third subtitle, so the phrase stands there
        assert _positions(conn, 20) == ([0, 3, 0, 3, 15], [0, 3, 0, 3, 9])

        assert documents[103] == {"blocks": [
            {"type": "paragraph", "mode": "flow", "lines": [{"text": "Chapter one."}]},
            {"type": "paragraph", "mode": "flow", "lines": [{"text": "It went on."}]},
        ]}

    command.downgrade(cfg, "0044")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM source_documents")).scalar() == 0
        assert _positions(conn, 10) == (None, None)
