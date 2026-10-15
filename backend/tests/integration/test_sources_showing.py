"""Which sources show a lemma among the words of their shown phrases (`phrase_words`)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Phrase, Word
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.phrase_writes import PhraseWords
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import text

from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

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
    _shows(db_session, phrase_id_of(1), "he", "glare")
    insert_word(db_session, 2, source_id=2, lemma="stare")
    _shows(db_session, phrase_id_of(2), "stare", "glare")
    insert_word(db_session, 3, source_id=3, lemma="gaze")
    _shows(db_session, phrase_id_of(3), "gaze", "glare")
    db_session.execute(
        text("UPDATE phrases SET shown_by = NULL WHERE id = :id"), {"id": phrase_id_of(3)},
    )

    showing = SqlaOccurrenceRepository(db_session).sources_showing({"Glare"})

    assert showing == {1, 2}


def test_no_lemmas_no_sources(db_session: Session) -> None:
    assert SqlaOccurrenceRepository(db_session).sources_showing(set()) == set()


def test_phrase_words_are_kept_lowercase(db_session: Session) -> None:
    """A phrase stored with a capitalised lemma (older data) still lands lowercase."""
    insert_source(db_session, 1)
    insert_word(db_session, 1, source_id=1, lemma="paris")
    stored = Phrase(
        text="Paris", words=(Word(0, 5, "Paris", CEFRLevel.A1, 3.0, content=True),),
        target=(0,),
    )

    PhraseWords(db_session).rewrite({phrase_id_of(1): dump_phrase(stored)})

    lemmas = db_session.scalars(
        text("SELECT lemma FROM phrase_words WHERE phrase_id = :id"), {"id": phrase_id_of(1)},
    )
    assert all(lemma == lemma.lower() for lemma in lemmas)
    assert SqlaOccurrenceRepository(db_session).sources_showing({"Paris"}) == {1}
