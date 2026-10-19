"""Migration 0049 turns every card into a word and its phrase, merging words of one lemma,
and every card's decision into its one choice (design §4)."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.domain.value_objects.card_choice import Press
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.decision_support import Decisions
from tests.migration_0049_checks import Before, app_export_queue, check_upgraded, read_before
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0048"
REVISION_UNDER_TEST = "0049"

CONTENT_SOURCE = 11
TOPIC_SOURCE = 12
EXPORTED_PAIR_SOURCE = 13
PROCESSING_SOURCE = 14

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
CARD_O = 15  # KNOWN, its Known put the lemma into known words
CARD_P = 16  # KNOWN, its lemma is not in known words
CARD_Q = 17  # phrasal verb whose stored target lists the particle first

# One card per row of the §4 mapping table, in ROWS_SOURCE.
ROWS_SOURCE = 15
EXPORTED_LEARN_KNOWN = 101    # learn, exported, lemma in Known → KNOWN, active
EXPORTED_KNOWN_CLOZE = 102    # known, exported, lemma in Known, cloze markup → KNOWN, cloze row
EXPORTED_LEARN_UNKNOWN = 103  # learn, exported, lemma in Known and Unknown → NONE, released
EXPORTED_LEARN_NEITHER = 104  # learn, exported, lemma in neither → NONE, released
EXPORTED_PENDING = 105        # pending, exported → NONE, released
EXPORTED_SKIP = 106           # skip, exported → SKIP, released
LEARN_CLOZE = 107             # learn, cloze markup, not exported → CLOZE
KNOWN_UNKNOWN = 108           # known, not exported, lemma in Unknown → NONE
SKIP_ALONE = 109              # skip → SKIP
LEARN_WINNER = 110            # learn; its newer duplicate is skipped
SKIP_LOSER = 111              # skip, loses to LEARN_WINNER → SKIP
LEARN_LOSER = 112             # learn, loses to KNOWN_WINNER (Known over Learn) → NONE, logged
KNOWN_WINNER = 113            # known, lemma in Known → KNOWN
LEARN_LISTED = 114            # learn, not exported, lemma in Known → LEARN, reads Known (Q15)
ROW_CARDS = {
    EXPORTED_LEARN_KNOWN: ("abide", "learn", 501),
    EXPORTED_KNOWN_CLOZE: ("bask", "known", 502),
    EXPORTED_LEARN_UNKNOWN: ("cower", "learn", 503),
    EXPORTED_LEARN_NEITHER: ("dwell", "learn", 504),
    EXPORTED_PENDING: ("evade", "pending", 505),
    EXPORTED_SKIP: ("fret", "skip", 506),
    LEARN_CLOZE: ("gnaw", "learn", None),
    KNOWN_UNKNOWN: ("heed", "known", None),
    SKIP_ALONE: ("irk", "skip", None),
    LEARN_WINNER: ("jolt", "learn", None),
    SKIP_LOSER: ("Jolt", "skip", None),
    LEARN_LOSER: ("knead", "learn", None),
    KNOWN_WINNER: ("knead", "known", None),
    LEARN_LISTED: ("loom", "learn", None),
}
ROWS_KNOWN = ("abide", "bask", "cower", "knead", "loom")
ROWS_UNKNOWN = ("cower", "heed")
CARD_COUNT = 17 + len(ROW_CARDS)

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
    conn.execute(
        text(
            "UPDATE candidates SET origin_kind = 'source', origin_title = 'Book'"
            " WHERE id = :id"
        ),
        {"id": CARD_TOPIC},
    )
    _source(conn, PROCESSING_SOURCE, "content")
    conn.execute(
        text(
            "UPDATE sources SET status = 'processing', processing_stage = 'analyzing_text'"
            " WHERE id = :id"
        ),
        {"id": PROCESSING_SOURCE},
    )
    # A stored review status, as the old app wrote it after decisions.
    conn.execute(
        text("UPDATE sources SET status = 'reviewed' WHERE id = :id"), {"id": CONTENT_SOURCE},
    )
    conn.execute(
        text("UPDATE sources SET status = 'partially_reviewed' WHERE id = :id"),
        {"id": TOPIC_SOURCE},
    )
    conn.execute(text("INSERT INTO known_words (lemma, created_at) VALUES ('old', '2026-01-01')"))

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
    for card_id, lemma in ((CARD_O, "ponder"), (CARD_P, "muse")):
        _card(
            conn, card_id, EXPORTED_PAIR_SOURCE, lemma, "known",
            _stored_phrase(f"They {lemma}.", lemma), [0, card_id, 0, card_id, 12],
        )
    conn.execute(text(
        "INSERT INTO known_words (lemma, pos, created_at) VALUES ('ponder', 'VERB', '2026-01-01')"
    ))
    gave_it_up = json.loads(_stored_phrase("They gave it up.", "gave"))
    gave_it_up["target"] = [3, 1]
    _card(
        conn, CARD_Q, EXPORTED_PAIR_SOURCE, "give up", "pending", json.dumps(gave_it_up),
        [0, CARD_Q, 0, CARD_Q, 16],
    )
    _seed_mapping_rows(conn)


def _seed_mapping_rows(conn: Connection) -> None:
    _source(conn, ROWS_SOURCE, "content")
    for card_id, (lemma, status, note) in ROW_CARDS.items():
        sentence = f"They {lemma.lower()} {card_id}."
        _card(
            conn, card_id, ROWS_SOURCE, lemma, status, _stored_phrase(sentence, lemma.lower()),
            [0, card_id, 0, card_id, len(sentence)],
        )
        if note is not None:
            _synced(conn, card_id, note)
    for card_id in (EXPORTED_KNOWN_CLOZE, LEARN_CLOZE):
        conn.execute(
            text(
                "INSERT INTO candidate_clozes (candidate_id, hidden_word_indices, hint_kind,"
                " phrase) VALUES (:id, '[1]', 'none', 'x')"
            ),
            {"id": card_id},
        )
    for lemma in ROWS_KNOWN:
        conn.execute(
            text(
                "INSERT INTO known_words (lemma, pos, created_at)"
                " VALUES (:l, 'VERB', '2026-01-01')"
            ),
            {"l": lemma},
        )
    for lemma in ROWS_UNKNOWN:
        conn.execute(
            text("INSERT INTO unknown_words (lemma, created_at) VALUES (:l, '2026-01-01')"),
            {"l": lemma},
        )


@dataclass(frozen=True)
class Migrated:
    url: str
    path: Path
    before: Before
    started: datetime
    finished: datetime
    dropped: list[int]


@pytest.fixture
def migrated(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> Migrated:
    path = tmp_path / "app.db"
    url = f"sqlite:///{path}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, REVISION_BEFORE)
    with create_engine(url).begin() as conn:
        _seed(conn)
    with sqlite3.connect(path) as conn:
        before = read_before(conn)
    caplog.set_level(logging.WARNING)
    started = datetime.now(tz=UTC).replace(tzinfo=None)
    command.upgrade(cfg, REVISION_UNDER_TEST)
    finished = datetime.now(tz=UTC).replace(tzinfo=None)
    return Migrated(url, path, before, started, finished, dropped_decisions(caplog))


def dropped_decisions(caplog: pytest.LogCaptureFixture) -> list[int]:
    """The card ids the migration logged as merge losers whose decision it dropped."""
    return [
        int(record.args[1])  # type: ignore[index]
        for record in caplog.records
        if record.msg.startswith("0049: merge dropped")
    ]


@pytest.fixture
def db_url(migrated: Migrated) -> str:
    return migrated.url


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
    assert [w["id"] for w in words if w["id"] < min(ROW_CARDS)] == [
        CARD_A, CARD_D, CARD_TOPIC, CARD_SPANNING, CARD_H, CARD_I, CARD_K, CARD_N, CARD_O,
        CARD_P, CARD_Q,
    ]
    assert len(_rows(db_url, "SELECT id FROM phrases")) == CARD_COUNT


def test_undoing_a_migrated_known_takes_the_lemma_out_of_known(db_url: str) -> None:
    engine = create_engine(db_url)
    phrase_id = _phrase_of(db_url, CARD_O, "They ponder")["id"]
    assert isinstance(phrase_id, int)
    with Session(engine) as session:
        Decisions(session).decide_phrase().press(phrase_id, Press.KNOWN)
        session.commit()
    assert _rows(db_url, "SELECT lemma FROM known_words WHERE lemma = 'ponder'") == []
    assert _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_O) == [
        {"status": "pending"},
    ]


def test_duplicate_of_an_exported_card_becomes_its_manual_phrase(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    b = _phrase_of(db_url, CARD_A, "Then he glared")
    assert (a["origin"], a["shown_by"]) == ("auto", "selection")
    assert (b["origin"], b["shown_by"]) == ("manual", "user")
    # Exported Learn whose lemma is not in Known: the user removed Known after the export.
    assert (a["choice"], b["choice"]) == ("none", "none")
    assert (a["block"], a["line"], a["char"]) == (PARAGRAPH, 0, LINE_0.index("glared"))


def test_results_are_keyed_by_the_phrase_of_their_card(db_url: str) -> None:
    a = _phrase_of(db_url, CARD_A, LINE_0)
    b = _phrase_of(db_url, CARD_A, "Then he glared")
    meanings = {
        r["phrase_id"]: r["meaning"]
        for r in _rows(db_url, "SELECT phrase_id, meaning FROM candidate_meanings")
    }
    assert meanings == {a["id"]: "to look angrily", b["id"]: "to stare"}
    clozes = {r["phrase_id"] for r in _rows(db_url, "SELECT phrase_id FROM candidate_clozes")}
    assert a["id"] in clozes
    assert b["id"] not in clozes
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
        db_url, "SELECT candidate_id, phrase_id, anki_note_id, lemma, pos, note_kind,"
        " released_at IS NOT NULL AS released FROM anki_synced_cards"
        " WHERE anki_note_id IN (:a, :g, :h) ORDER BY anki_note_id",
        a=NOTE_A, g=NOTE_G, h=NOTE_H,
    )
    g = _phrase_of(db_url, CARD_H, "They linger")
    h = _phrase_of(db_url, CARD_H, "We linger")
    a = _phrase_of(db_url, CARD_A, LINE_0)
    assert synced == [
        {"candidate_id": CARD_A, "phrase_id": a["id"], "anki_note_id": NOTE_A,
         "lemma": "glare", "pos": "VERB", "note_kind": "cloze", "released": 1},
        {"candidate_id": CARD_H, "phrase_id": g["id"], "anki_note_id": NOTE_G,
         "lemma": "linger", "pos": "VERB", "note_kind": "learn", "released": 1},
        {"candidate_id": CARD_H, "phrase_id": h["id"], "anki_note_id": NOTE_H,
         "lemma": "linger", "pos": "VERB", "note_kind": "learn", "released": 1},
    ]
    assert (h["choice"], g["choice"]) == ("none", "none")


def test_a_decision_beats_a_newer_undecided_duplicate(db_url: str) -> None:
    words = _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_I)
    assert words == [{"status": "learn"}]
    i = _phrase_of(db_url, CARD_I, "They wander")
    j = _phrase_of(db_url, CARD_I, "We wander")
    assert (i["choice"], j["choice"]) == ("learn", "none")
    assert (j["origin"], j["shown_by"]) == ("manual", "user")


def test_skipped_original_of_an_example_is_released(db_url: str) -> None:
    c = _phrase_of(db_url, CARD_D, "again and left")
    d = _phrase_of(db_url, CARD_D, "She left early")
    assert (c["origin"], c["choice"], c["shown_by"]) == ("auto", "none", None)
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


def test_a_collected_phrase_keeps_where_its_card_came_from(db_url: str) -> None:
    topic = _phrase_of(db_url, CARD_TOPIC, "What a serendipity")
    assert (topic["collected_kind"], topic["collected_title"]) == ("source", "Book")
    a = _phrase_of(db_url, CARD_A, LINE_0)
    assert (a["collected_kind"], a["collected_title"]) == (None, None)


def test_a_source_left_processing_is_new_again_and_no_stage_is_stored(db_url: str) -> None:
    [source] = _rows(db_url, "SELECT status FROM sources WHERE id = :id", id=PROCESSING_SOURCE)
    assert source["status"] == "new"
    columns = {c["name"] for c in inspect(create_engine(db_url)).get_columns("sources")}
    assert "processing_stage" not in columns
    operation_columns = {
        c["name"] for c in inspect(create_engine(db_url)).get_columns("source_operations")
    }
    assert "stage" in operation_columns


def test_a_stored_review_status_becomes_done_it_is_derived_on_read(db_url: str) -> None:
    rows = _rows(
        db_url, "SELECT status FROM sources WHERE id IN (:a, :b)",
        a=CONTENT_SOURCE, b=TOPIC_SOURCE,
    )
    assert [row["status"] for row in rows] == ["done", "done"]


def test_known_words_keep_no_anki_progress_and_there_is_no_note_table(db_url: str) -> None:
    engine = inspect(create_engine(db_url))
    assert {c["name"] for c in engine.get_columns("known_words")} == {
        "id", "lemma", "pos", "created_at",
    }
    assert "anki_notes" not in engine.get_table_names()


def test_a_binding_is_kept_with_no_card_or_word(db_url: str) -> None:
    columns = {
        c["name"]: c for c in inspect(create_engine(db_url)).get_columns("anki_synced_cards")
    }
    assert set(columns) == {
        "id", "candidate_id", "phrase_id", "anki_note_id", "lemma", "pos", "note_kind",
        "learning_since", "released_at",
    }
    assert columns["candidate_id"]["nullable"] and columns["phrase_id"]["nullable"]
    keys = inspect(create_engine(db_url)).get_foreign_keys("anki_synced_cards")
    assert {(k["referred_table"], k["options"].get("ondelete")) for k in keys} == {
        ("candidates", "SET NULL"), ("phrases", "SET NULL"),
    }


def test_target_on_the_next_line_is_keyed_on_that_line(db_url: str) -> None:
    spanning = _phrase_of(db_url, CARD_SPANNING, "glared at me. Then")
    assert (spanning["block"], spanning["line"], spanning["char"]) == (PARAGRAPH, 1, 0)


def test_the_key_is_where_the_first_word_of_the_target_starts(db_url: str) -> None:
    """As the analysis keys an occurrence: the earliest target word, in whatever order the
    stored target lists them."""
    q = _phrase_of(db_url, CARD_Q, "They gave it up")
    assert (q["block"], q["line"], q["char"]) == (0, CARD_Q, "They gave it up.".index("gave"))


def test_partial_and_expression_indexes_exist(db_url: str) -> None:
    indexes = {
        str(r["name"]): str(r["sql"])
        for r in _rows(db_url, "SELECT name, sql FROM sqlite_master WHERE type = 'index'"
                       " AND sql IS NOT NULL")
    }
    assert "WHERE" in indexes["ux_phrases_auto_key"]
    assert "choice IN ('learn', 'cloze', 'known')" in indexes["ux_phrases_decision"]
    assert "released_at IS NULL" in indexes["ux_anki_synced_cards_active"]
    assert "lower(" in indexes["ux_candidates_word"]


def test_word_and_phrase_ids_are_never_reused(db_url: str) -> None:
    tables = {
        str(r["name"]): str(r["sql"])
        for r in _rows(db_url, "SELECT name, sql FROM sqlite_master WHERE type = 'table'")
    }
    assert "AUTOINCREMENT" in tables["candidates"]
    assert "AUTOINCREMENT" in tables["phrases"]
    assert "enrichment_cache" not in tables  # dropped together with Reprocess


def test_new_tables_exist(db_url: str) -> None:
    names = set(inspect(create_engine(db_url)).get_table_names())
    assert {"phrases", "document_parses", "source_operations"} <= names
    assert "_card_phrase" not in names
    assert "phrase_words" not in names
    candidate_columns = {
        c["name"] for c in inspect(create_engine(db_url)).get_columns("candidates")
    }
    assert not candidate_columns & {
        "source_phrase", "polished_phrase", "polish_reverted", "phrase_position",
        "origin_kind", "origin_title",
    }


def test_no_row_points_at_a_merged_away_word(db_url: str) -> None:
    assert _rows(db_url, "PRAGMA foreign_key_check") == []
    assert len(_rows(db_url, "SELECT id FROM anki_synced_cards")) == 4 + len(  # A G H K
        [note for _, _, note in ROW_CARDS.values() if note is not None]
    )


def test_an_exported_duplicate_beats_a_decision_and_the_dropped_decision_is_logged(
    migrated: Migrated,
) -> None:
    """§4 merge winner: an exported card first. Its export keeps its phrase; L's Learn is
    dropped, and the log names it."""
    db_url = migrated.url
    words = _rows(db_url, "SELECT status FROM candidates WHERE id = :w", w=CARD_K)
    assert words == [{"status": "pending"}]
    assert _rows(db_url, "SELECT id FROM candidates WHERE id = :w", w=CARD_L) == []
    decided = _phrase_of(db_url, CARD_K, "They drift")
    exported = _phrase_of(db_url, CARD_K, "We drift")
    assert (decided["choice"], exported["choice"]) == ("none", "none")
    synced = _rows(
        db_url, "SELECT candidate_id, phrase_id, released_at IS NOT NULL AS released"
        " FROM anki_synced_cards WHERE anki_note_id = :n",
        n=NOTE_K,
    )
    assert synced == [{"candidate_id": CARD_K, "phrase_id": exported["id"], "released": 1}]
    assert CARD_L in migrated.dropped


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


# ── §4: one test per row of the mapping table ─────────────────────────


def _card_row(db_url: str, card_id: int) -> tuple[object, object, list[tuple[object, ...]]]:
    """The choice of the card's phrase, its word's status, and its export records as
    (note kind, active)."""
    lemma, _, _ = ROW_CARDS[card_id]
    sentence = f"They {lemma.lower()} {card_id}."
    [found] = [
        r for r in _rows(
            db_url,
            "SELECT p.id, p.choice, c.status FROM phrases p JOIN candidates c"
            " ON c.id = p.candidate_id WHERE c.source_id = :s", s=ROWS_SOURCE,
        )
        if json.loads(str(_rows(
            db_url, "SELECT source_phrase FROM phrases WHERE id = :p", p=r["id"],
        )[0]["source_phrase"]))["text"] == sentence
    ]
    bindings = [
        (r["note_kind"], r["active"]) for r in _rows(
            db_url, "SELECT note_kind, released_at IS NULL AS active FROM anki_synced_cards"
            " WHERE phrase_id = :p", p=found["id"],
        )
    ]
    return found["choice"], found["status"], bindings


@pytest.mark.parametrize(
    ("card_id", "expected"),
    [
        (EXPORTED_LEARN_KNOWN, ("known", "known", [("learn", 1)])),
        (EXPORTED_KNOWN_CLOZE, ("known", "known", [("cloze", 1)])),
        (EXPORTED_LEARN_UNKNOWN, ("none", "pending", [("learn", 0)])),
        (EXPORTED_LEARN_NEITHER, ("none", "pending", [("learn", 0)])),
        (EXPORTED_PENDING, ("none", "pending", [("learn", 0)])),
        (EXPORTED_SKIP, ("skip", "pending", [("learn", 0)])),
        (LEARN_CLOZE, ("cloze", "learn", [])),
        (KNOWN_UNKNOWN, ("none", "pending", [])),
        (SKIP_ALONE, ("skip", "pending", [])),
        (LEARN_WINNER, ("learn", "learn", [])),
        (SKIP_LOSER, ("skip", "learn", [])),
        (LEARN_LOSER, ("none", "known", [])),
        (KNOWN_WINNER, ("known", "known", [])),
        (LEARN_LISTED, ("learn", "learn", [])),
    ],
)
def test_every_mapping_row(
    db_url: str, card_id: int, expected: tuple[object, object, list[tuple[object, ...]]],
) -> None:
    assert _card_row(db_url, card_id) == expected


def test_every_export_starts_its_timer_at_the_migration(migrated: Migrated) -> None:
    since = {
        datetime.fromisoformat(str(r["learning_since"]))
        for r in _rows(migrated.url, "SELECT learning_since FROM anki_synced_cards")
    }
    [moment] = since
    assert migrated.started <= moment <= migrated.finished


def test_the_decided_merge_losers_are_logged(migrated: Migrated) -> None:
    assert sorted(migrated.dropped) == [CARD_G, CARD_L, LEARN_LOSER]


def test_the_migrated_database_meets_every_prod_copy_assert(migrated: Migrated) -> None:
    """§4.1 on the synthetic fixture: the same asserts as the prod-copy test."""
    with sqlite3.connect(migrated.path) as conn:
        report = check_upgraded(
            conn, migrated.before, migrated.started, migrated.finished, migrated.dropped,
            app_export_queue(migrated.path),
        )
    assert report.counts["active binding on a KNOWN card"] == 2  # noqa: PLR2004 — 101 102
    assert report.listed["old SKIP: released original → NONE"] == [CARD_C]
    assert report.listed[
        "old LEARN not exported, lemma in Known: reads Known (Q15)"
    ] == [LEARN_LISTED]


def test_the_downgrade_raises_as_declared(migrated: Migrated) -> None:
    with pytest.raises(NotImplementedError):
        command.downgrade(_alembic_config(migrated.url), REVISION_BEFORE)
