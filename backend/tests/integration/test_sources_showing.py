"""Which sources show a lemma among the words of their shown phrases (`phrase_words`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import text

from tests.integration.conftest import insert_source
from tests.word_support import insert_word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _shows(session: Session, phrase_id: int, *lemmas: str) -> None:
    for lemma in lemmas:
        session.execute(
            text("INSERT INTO phrase_words (phrase_id, lemma) VALUES (:id, :lemma)"),
            {"id": phrase_id, "lemma": lemma},
        )


def test_only_sources_whose_shown_phrases_have_the_lemma(db_session: Session) -> None:
    for source in (1, 2, 3):
        insert_source(db_session, source)
    insert_word(db_session, 1, source_id=1, lemma="glare")
    _shows(db_session, 1, "he", "glare")
    insert_word(db_session, 2, source_id=2, lemma="stare")
    _shows(db_session, 2, "stare", "glare")
    insert_word(db_session, 3, source_id=3, lemma="gaze")
    _shows(db_session, 3, "gaze", "glare")
    db_session.execute(text("UPDATE phrases SET shown_by = NULL WHERE id = 3"))

    showing = SqlaOccurrenceRepository(db_session).sources_showing({"Glare"})

    assert showing == {1, 2}


def test_no_lemmas_no_sources(db_session: Session) -> None:
    assert SqlaOccurrenceRepository(db_session).sources_showing(set()) == set()
