"""Migration 0050: each binding gets the choice of its card; an orphan, its note kind."""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from backend.infrastructure.persistence import database
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

pytestmark = pytest.mark.integration

KNOWN_WORD, LEARN_WORD = 1, 2
SOURCE = 100  # the migrations seed built-in sources


def _config(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(database.__file__).parent.parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _bind(session: Session, word_id: int | None, phrase_id: int | None, kind: str) -> None:
    session.execute(text(
        "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma, pos,"
        " note_kind, learning_since) VALUES (:w, :p, 1, 'glare', 'NOUN', :k,"
        " '2026-10-01 00:00:00')"
    ), {"w": word_id, "p": phrase_id, "k": kind})


def test_a_binding_takes_its_cards_choice_and_an_orphan_its_note_kind(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _config(db_url)
    command.upgrade(cfg, "0049")
    engine = create_engine(db_url)
    with Session(engine) as session:
        insert_source(session, SOURCE)
        insert_word(session, KNOWN_WORD, source_id=SOURCE, lemma="glare")
        insert_word(session, LEARN_WORD, source_id=SOURCE, lemma="linger")
        session.execute(text("UPDATE phrases SET choice = 'known' WHERE id = :id"),
                        {"id": phrase_id_of(KNOWN_WORD)})
        session.execute(text("UPDATE phrases SET choice = 'cloze' WHERE id = :id"),
                        {"id": phrase_id_of(LEARN_WORD)})
        _bind(session, KNOWN_WORD, phrase_id_of(KNOWN_WORD), "learn")
        _bind(session, LEARN_WORD, phrase_id_of(LEARN_WORD), "cloze")
        _bind(session, None, None, "cloze")
        session.commit()

    command.upgrade(cfg, "0050")

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT card_choice FROM anki_synced_cards ORDER BY id"
        )).scalars().all()
    assert rows == ["known", "cloze", "cloze"]

    command.downgrade(cfg, "0049")
    columns = {c["name"] for c in inspect(create_engine(db_url)).get_columns(
        "anki_synced_cards",
    )}
    assert "card_choice" not in columns
