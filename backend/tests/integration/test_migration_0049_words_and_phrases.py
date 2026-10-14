"""Migration 0049 turns every card into a word and its phrase, merging words of one lemma."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0048"
REVISION_UNDER_TEST = "0049"

CONTENT_SOURCE = 11
TOPIC_SOURCE = 12
EXPORTED_PAIR_SOURCE = 13

CARD_A = 1  # auto, LEARN, cloze, meaning, synced note 111, running MEANING job
CARD_B = 2  # same lemma as A in another case, PENDING, meaning
CARD_C = 3  # SKIP, its lemma got an example
CARD_D = 4  # the example of C's lemma
CARD_TOPIC = 5
CARD_SPANNING = 6  # its phrase starts on one line and its target on the next
CARD_G = 7  # exported, LEARN
CARD_H = 8  # exported, LEARN, same lemma as G
CARD_I = 9  # LEARN, not exported
CARD_J = 10  # PENDING, same lemma as I, newer
CARD_L = 11  # LEARN, not exported
CARD_K = 12  # exported, PENDING again, same lemma as L, newer
CARD_M = 13  # pronunciation and picture
CARD_N = 14  # same lemma as M, newer, its own pronunciation and picture
CARD_COUNT = 14

NOTE_A = 111
NOTE_G = 222
NOTE_H = 333
NOTE_K = 444

LINE_0 = "He glared at me."
LINE_1 = "Then he glared again and left."
DOCUMENT = {
    "blocks": [
        {"type": "heading", "level": 1, "text": "Title"},
        {"type": "paragraph", "mode": "flow", "lines": [{"text": LINE_0}, {"text": LINE_1}]},
    ]
}
PARAGRAPH = 1


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _stored_phrase(phrase_text: str, target: str) -> str:
    built = phrase(phrase_text, target)
    return json.dumps({
        "text": built.text,
        "words": [
            [w.start, w.end, w.lemma, w.level.name, w.zipf, w.content] for w in built.words
        ],
        "target": list(built.target),
    })


def _source(conn: Connection, source_id: int, role: str) -> None:
    conn.execute(
        text(
            "INSERT INTO sources (id, title, status, created_at, role)"
            " VALUES (:id, 'title', 'done', '2026-01-01 00:00:00', :role)"
        ),
        {"id": source_id, "role": role},
    )


def _card(
    conn: Connection,
    card_id: int,
    source_id: int,
    lemma: str,
    status: str,
    phrase_json: str,
    position: list[int] | None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " source_phrase, occurrences, status, is_phrasal_verb, phrase_position)"
            " VALUES (:id, :source_id, :lemma, 'VERB', 3.0, 0, :phrase, 1, :status, 0,"
            " :position)"
        ),
        {
            "id": card_id, "source_id": source_id, "lemma": lemma, "status": status,
            "phrase": phrase_json,
            "position": json.dumps(position) if position is not None else None,
        },
    )


def _meaning(conn: Connection, card_id: int, meaning: str, ipa: str | None = None) -> None:
    conn.execute(
        text(
            "INSERT INTO candidate_meanings (candidate_id, meaning, ipa)"
            " VALUES (:id, :meaning, :ipa)"
        ),
        {"id": card_id, "meaning": meaning, "ipa": ipa},
    )


def _synced(conn: Connection, card_id: int, note_id: int) -> None:
    conn.execute(
        text("INSERT INTO anki_synced_cards (candidate_id, anki_note_id) VALUES (:c, :n)"),
        {"c": card_id, "n": note_id},
    )


def _seed(conn: Connection) -> None:
    _source(conn, CONTENT_SOURCE, "content")
    conn.execute(
        text("INSERT INTO source_documents (source_id, document) VALUES (:id, :doc)"),
        {"id": CONTENT_SOURCE, "doc": json.dumps(DOCUMENT)},
    )
    _card(
        conn, CARD_A, CONTENT_SOURCE, "glare", "learn",
        _stored_phrase(LINE_0, "glared"), [PARAGRAPH, 0, 0, 0, len(LINE_0)],
    )
    _card(
        conn, CARD_B, CONTENT_SOURCE, "Glare", "pending",
        _stored_phrase("Then he glared again", "glared"), [PARAGRAPH, 1, 0, 1, 20],
    )
    _card(
        conn, CARD_C, CONTENT_SOURCE, "leave", "skip",
        _stored_phrase("again and left.", "left"), [PARAGRAPH, 1, 15, 1, len(LINE_1)],
    )
    _card(
        conn, CARD_D, CONTENT_SOURCE, "leave", "pending",
        _stored_phrase("She left early.", "left"), None,
    )
    _card(
        conn, CARD_SPANNING, CONTENT_SOURCE, "then", "pending",
        _stored_phrase("glared at me. Then he", "Then"), [PARAGRAPH, 0, 3, 1, 7],
    )
    conn.execute(
        text(
            "INSERT INTO candidate_clozes (candidate_id, hidden_word_indices, hint_kind, phrase)"
            " VALUES (:id, '[1]', 'none', :phrase)"
        ),
        {"id": CARD_A, "phrase": LINE_0},
    )
    _meaning(conn, CARD_A, "to look angrily", ipa="/ɡleə/")
    _meaning(conn, CARD_B, "to stare")
    _synced(conn, CARD_A, NOTE_A)
    conn.execute(
        text(
            "INSERT INTO jobs (job_type, candidate_id, source_id, status, created_at)"
            " VALUES ('meaning', :c, :s, 'running', '2026-01-01 00:00:00')"
        ),
        {"c": CARD_A, "s": CONTENT_SOURCE},
    )
    conn.execute(
        text(
            "INSERT INTO card_reports (source_id, source_title, candidate_id, lemma,"
            " context_fragment, zipf_frequency, fragment_unknown_count, is_phrasal_verb,"
            " comment, created_at)"
            " VALUES (:s, 'title', :c, 'glare', 'ctx', 3.0, 0, 0, '', '2026-01-01 00:00:00')"
        ),
        {"s": CONTENT_SOURCE, "c": CARD_B},
    )

    _source(conn, TOPIC_SOURCE, "topic")
    _card(
        conn, CARD_TOPIC, TOPIC_SOURCE, "serendipity", "pending",
        _stored_phrase("What a serendipity.", "serendipity"), None,
    )

    _source(conn, EXPORTED_PAIR_SOURCE, "content")
    _card(
        conn, CARD_G, EXPORTED_PAIR_SOURCE, "linger", "learn",
        _stored_phrase("They linger.", "linger"), [0, 0, 0, 0, 12],
    )
    _card(
        conn, CARD_H, EXPORTED_PAIR_SOURCE, "linger", "learn",
        _stored_phrase("We linger here.", "linger"), [0, 1, 0, 1, 15],
    )
    _synced(conn, CARD_G, NOTE_G)
    _synced(conn, CARD_H, NOTE_H)
    _card(
        conn, CARD_I, EXPORTED_PAIR_SOURCE, "wander", "learn",
        _stored_phrase("They wander.", "wander"), [0, 2, 0, 2, 12],
    )
    _card(
        conn, CARD_J, EXPORTED_PAIR_SOURCE, "wander", "pending",
        _stored_phrase("We wander off.", "wander"), [0, 3, 0, 3, 14],
    )
    _card(
        conn, CARD_L, EXPORTED_PAIR_SOURCE, "drift", "learn",
        _stored_phrase("They drift.", "drift"), [0, 4, 0, 4, 11],
    )
    _card(
        conn, CARD_K, EXPORTED_PAIR_SOURCE, "drift", "pending",
        _stored_phrase("We drift away.", "drift"), [0, 5, 0, 5, 14],
    )
    _synced(conn, CARD_K, NOTE_K)
    for card_id, text_ in ((CARD_M, "They roam."), (CARD_N, "We roam far.")):
        _card(
            conn, card_id, EXPORTED_PAIR_SOURCE, "roam", "pending",
            _stored_phrase(text_, "roam"), [0, card_id, 0, card_id, len(text_)],
        )
        conn.execute(
            text(
                "INSERT INTO candidate_pronunciations (candidate_id, us_audio_path)"
                " VALUES (:c, :p)"
            ),
            {"c": card_id, "p": f"/us/{card_id}.mp3"},
        )
        conn.execute(
            text(
                "INSERT INTO candidate_meaning_images (candidate_id, image_path)"
                " VALUES (:c, :p)"
            ),
            {"c": card_id, "p": f"/img/{card_id}.webp"},
        )


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, REVISION_BEFORE)
    with create_engine(url).begin() as conn:
        _seed(conn)
    command.upgrade(cfg, REVISION_UNDER_TEST)
    return url


def _rows(db_url: str, sql: str, **params: object) -> list[dict[str, object]]:
    with create_engine(db_url).connect() as conn:
        return [dict(row._mapping) for row in conn.execute(text(sql), params)]


def _phrase_of(db_url: str, word_id: int, text_start: str) -> dict[str, object]:
    for row in _rows(db_url, "SELECT * FROM phrases WHERE candidate_id = :w", w=word_id):
        if json.loads(str(row["source_phrase"]))["text"].startswith(text_start):
            return row
    raise AssertionError(f"No phrase {text_start!r} of word {word_id}")


def test_one_word_per_lemma_and_every_card_is_a_phrase(db_url: str) -> None:
    words = _rows(db_url, "SELECT id, lemma, status FROM candidates ORDER BY id")
    assert [w["id"] for w in words] == [
        CARD_A, CARD_D, CARD_TOPIC, CARD_SPANNING, CARD_H, CARD_I, CARD_L, CARD_N,
    ]
    assert len(_rows(db_url, "SELECT id FROM phrases")) == CARD_COUNT


def test_duplicate_of_an_exported_card_becomes_its_manual_phrase(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    b = _phrase_of(db_url, CARD_A, "Then he glared")
    assert (a["origin"], a["shown_by"]) == ("auto", "selection")
    assert (b["origin"], b["shown_by"]) == ("manual", "user")
    assert (a["is_decision"], a["decision_kind"]) == (1, "cloze")
    assert not b["is_decision"]
    assert (a["block"], a["line"], a["char"]) == (PARAGRAPH, 0, LINE_0.index("glared"))


def test_results_are_keyed_by_the_phrase_of_their_card(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    b = _phrase_of(db_url, CARD_A, "Then he glared")
    meanings = {
        r["phrase_id"]: r["meaning"]
        for r in _rows(db_url, "SELECT phrase_id, meaning FROM candidate_meanings")
    }
    assert meanings == {a["id"]: "to look angrily", b["id"]: "to stare"}
    clozes = _rows(db_url, "SELECT phrase_id FROM candidate_clozes")
    assert clozes == [{"phrase_id": a["id"]}]
    assert "candidate_id" not in {
        c["name"] for c in inspect(create_engine(db_url)).get_columns("candidate_meanings")
    }


def test_ipa_moves_to_the_pronunciation_of_the_word(db_url: str) -> None:
    rows = _rows(
        db_url, "SELECT candidate_id, ipa FROM candidate_pronunciations WHERE ipa IS NOT NULL",
    )
    assert rows == [{"candidate_id": CARD_A, "ipa": "/ɡleə/"}]


def test_running_job_and_report_point_at_the_phrase_of_their_card(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    b = _phrase_of(db_url, CARD_A, "Then he glared")
    jobs = _rows(db_url, "SELECT candidate_id, phrase_id, phrase_revision, status FROM jobs")
    assert jobs == [
        {"candidate_id": CARD_A, "phrase_id": a["id"], "phrase_revision": 0, "status": "running"},
    ]
    reports = _rows(db_url, "SELECT candidate_id, phrase_id FROM card_reports")
    assert reports == [{"candidate_id": CARD_A, "phrase_id": b["id"]}]


def test_every_export_record_survives_with_its_phrase(db_url: str) -> None:
    synced = _rows(
        db_url, "SELECT candidate_id, phrase_id, anki_note_id FROM anki_synced_cards"
        " WHERE anki_note_id != :k ORDER BY anki_note_id", k=NOTE_K,
    )
    g = _phrase_of(db_url, CARD_H, "They linger")
    h = _phrase_of(db_url, CARD_H, "We linger")
    a = _phrase_of(db_url, CARD_A, LINE_0)
    assert synced == [
        {"candidate_id": CARD_A, "phrase_id": a["id"], "anki_note_id": NOTE_A},
        {"candidate_id": CARD_H, "phrase_id": g["id"], "anki_note_id": NOTE_G},
        {"candidate_id": CARD_H, "phrase_id": h["id"], "anki_note_id": NOTE_H},
    ]
    assert h["is_decision"] and not g["is_decision"]
    notes = _rows(db_url, "SELECT note_id, lemma, matured_at FROM anki_notes ORDER BY note_id")
    assert [(n["note_id"], n["lemma"]) for n in notes] == [
        (NOTE_A, "glare"), (NOTE_G, "linger"), (NOTE_H, "linger"), (NOTE_K, "drift"),
    ]
    assert all(n["matured_at"] is not None for n in notes)


def test_a_decision_beats_a_newer_undecided_duplicate(db_url: str) -> None:
    words = _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_I)
    assert words == [{"status": "learn"}]
    i = _phrase_of(db_url, CARD_I, "They wander")
    j = _phrase_of(db_url, CARD_I, "We wander")
    assert i["is_decision"] and not j["is_decision"]
    assert (j["origin"], j["shown_by"]) == ("manual", "user")


def test_skipped_original_of_an_example_is_released(db_url: str) -> None:
    c = _phrase_of(db_url, CARD_D, "again and left")
    d = _phrase_of(db_url, CARD_D, "She left early")
    assert (c["origin"], c["skipped"], c["shown_by"]) == ("auto", 0, None)
    assert (d["origin"], d["shown_by"], d["block"]) == ("example", "user", None)
    assert (c["replaces_selection"], d["replaces_selection"]) == (0, 1)
    words = _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_D)
    assert words == [{"status": "pending"}]


def test_only_an_example_that_took_a_skipped_original_replaces_a_selection(
    db_url: str,
) -> None:
    replacing = _rows(db_url, "SELECT candidate_id FROM phrases WHERE replaces_selection = 1")
    assert replacing == [{"candidate_id": CARD_D}]


def test_topic_phrase_is_collected(db_url: str) -> None:
    topic = _phrase_of(db_url, CARD_TOPIC, "What a serendipity")
    assert (topic["origin"], topic["shown_by"]) == ("collected", "user")


def test_target_on_the_next_line_is_keyed_on_that_line(db_url: str) -> None:
    spanning = _phrase_of(db_url, CARD_SPANNING, "glared at me. Then")
    assert (spanning["block"], spanning["line"], spanning["char"]) == (PARAGRAPH, 1, 0)


def test_phrase_words_are_the_words_of_the_shown_text(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    lemmas = {
        str(r["lemma"])
        for r in _rows(db_url, "SELECT lemma FROM phrase_words WHERE phrase_id = :p", p=a["id"])
    }
    assert lemmas == {"he", "glared", "at", "me"}


def test_partial_and_expression_indexes_exist(db_url: str) -> None:
    indexes = {
        str(r["name"]): str(r["sql"])
        for r in _rows(db_url, "SELECT name, sql FROM sqlite_master WHERE type = 'index'"
                       " AND sql IS NOT NULL")
    }
    assert "WHERE" in indexes["ux_phrases_auto_key"]
    assert "WHERE" in indexes["ux_phrases_decision"]
    assert "lower(" in indexes["ux_candidates_word"]
    assert "ix_phrase_words_lemma" in indexes


def test_word_and_phrase_ids_are_never_reused(db_url: str) -> None:
    tables = {
        str(r["name"]): str(r["sql"])
        for r in _rows(db_url, "SELECT name, sql FROM sqlite_master WHERE type = 'table'")
    }
    assert "AUTOINCREMENT" in tables["candidates"]
    assert "AUTOINCREMENT" in tables["phrases"]
    assert "enrichment_cache" in tables  # dropped together with Reprocess


def test_new_tables_exist(db_url: str) -> None:
    names = set(inspect(create_engine(db_url)).get_table_names())
    assert {
        "phrases", "phrase_words", "anki_notes", "document_parses", "source_operations",
        "known_word_removals",
    } <= names
    assert "_card_phrase" not in names
    candidate_columns = {
        c["name"] for c in inspect(create_engine(db_url)).get_columns("candidates")
    }
    assert not candidate_columns & {
        "source_phrase", "polished_phrase", "polish_reverted", "phrase_position",
    }


def test_no_row_points_at_a_merged_away_word(db_url: str) -> None:
    assert _rows(db_url, "PRAGMA foreign_key_check") == []
    assert len(_rows(db_url, "SELECT id FROM anki_synced_cards")) == 4  # noqa: PLR2004 — A G H K


def test_a_decision_beats_an_exported_duplicate_whose_export_keeps_its_phrase(
    db_url: str,
) -> None:
    words = _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_L)
    assert words == [{"status": "learn"}]
    assert _rows(db_url, "SELECT id FROM candidates WHERE id = :w", w=CARD_K) == []
    decided = _phrase_of(db_url, CARD_L, "They drift")
    exported = _phrase_of(db_url, CARD_L, "We drift")
    assert (decided["is_decision"], exported["is_decision"]) == (1, 0)
    synced = _rows(
        db_url, "SELECT candidate_id, phrase_id FROM anki_synced_cards WHERE anki_note_id = :n",
        n=NOTE_K,
    )
    assert synced == [{"candidate_id": CARD_L, "phrase_id": exported["id"]}]


def test_the_winner_keeps_its_own_pronunciation_and_picture(db_url: str) -> None:
    pronunciations = _rows(
        db_url, "SELECT candidate_id, us_audio_path FROM candidate_pronunciations"
        " WHERE candidate_id IN (:m, :n)", m=CARD_M, n=CARD_N,
    )
    assert pronunciations == [{"candidate_id": CARD_N, "us_audio_path": f"/us/{CARD_N}.mp3"}]
    images = _rows(
        db_url, "SELECT candidate_id, image_path FROM candidate_meaning_images"
        " WHERE candidate_id IN (:m, :n)", m=CARD_M, n=CARD_N,
    )
    assert images == [{"candidate_id": CARD_N, "image_path": f"/img/{CARD_N}.webp"}]
    orphans = _rows(
        db_url, "SELECT candidate_id FROM candidate_pronunciations"
        " WHERE candidate_id NOT IN (SELECT id FROM candidates)"
        " UNION ALL SELECT candidate_id FROM candidate_meaning_images"
        " WHERE candidate_id NOT IN (SELECT id FROM candidates)",
    )
    assert orphans == []
