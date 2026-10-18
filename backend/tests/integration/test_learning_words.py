"""Learn → learning: words waiting for export and words exported to Anki, in a real database."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.get_learning_words import GetLearningWordsUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.sqla_anki_note_repository import SqlaAnkiNoteRepository
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unknown_word_repository import (
    SqlaUnknownWordRepository,
)
from sqlalchemy import text

from tests.phrase_support import phrase
from tests.word_support import CREATED_AT, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOTE = 900
OTHER_PHRASE = 5000


class Bench:
    """The user's words over a real database."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.notes = SqlaAnkiNoteRepository(session)
        self.known = SqlaKnownWordRepository(session)
        self.learning = SqlaLearningQuery(session)
        self.vocabulary = UserVocabulary(
            known_word_repo=self.known,
            unknown_word_repo=SqlaUnknownWordRepository(session),
            learning_query=self.learning,
        )

    def exported_learn_word(self, word_id: int, lemma: str, note_id: int) -> None:
        insert_word(self.session, word_id, lemma=lemma, status=WordStatus.LEARN.value)
        SqlaAnkiSyncRepository(self.session).mark_synced(word_id, note_id, phrase_id_of(word_id))
        self.notes.add(note_id, lemma, "NOUN")

    def is_learning(self, lemma: str) -> bool:
        return self.vocabulary.snapshot().is_learning(lemma)

    def is_known(self, lemma: str) -> bool:
        return self.vocabulary.is_known(lemma)


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


def test_an_exported_learn_word_is_learning_not_known(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)

    assert bench.is_learning("glare")
    assert not bench.is_known("glare")


def test_a_learn_word_waiting_for_export_is_learning(bench: Bench) -> None:
    insert_word(bench.session, 1, lemma="linger", status=WordStatus.LEARN.value)

    assert bench.is_learning("linger")


def test_known_is_stronger_than_a_note_in_anki(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.known.add("glare", None)

    assert bench.is_known("glare")
    assert not bench.is_learning("glare")


def test_deleting_the_source_keeps_the_exported_word_learning(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    SqlaSourceRepository(bench.session).delete(1)
    bench.session.flush()

    assert bench.is_learning("glare")


def test_the_learning_list_tells_words_in_anki_from_words_waiting(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    insert_word(bench.session, 2, lemma="linger", status=WordStatus.LEARN.value)
    insert_word(bench.session, 3, lemma="wander", status=WordStatus.LEARN.value)
    bench.known.add("wander", None)

    learning = GetLearningWordsUseCase(bench.vocabulary, bench.learning).execute()

    assert learning.in_anki == ["glare"]
    assert learning.awaiting_export == ["linger"]


def test_every_exported_note_is_in_anki(bench: Bench) -> None:
    bench.notes.add(NOTE, "glare", "NOUN")
    bench.notes.add(NOTE + 1, "Drift", None)

    assert bench.learning.in_anki() == frozenset({"glare", "drift"})


def test_a_decision_phrase_waits_for_export_though_another_phrase_was_exported(
    bench: Bench,
) -> None:
    """A word merged from cards keeps the export record of a phrase that is not its
    decision: the decision phrase still goes to Anki."""
    insert_word(bench.session, 1, lemma="linger", status=WordStatus.LEARN.value)
    bench.session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, skipped,"
            " is_decision, created_at)"
            " VALUES (:id, 1, :phrase, 'manual', 'user', 0, 0, :created_at)"
        ),
        {"id": OTHER_PHRASE, "phrase": dump_phrase(phrase("We linger.", "linger")),
         "created_at": CREATED_AT},
    )
    SqlaAnkiSyncRepository(bench.session).mark_synced(1, NOTE, OTHER_PHRASE)

    assert bench.learning.awaiting_export() == frozenset({"linger"})
    queue = ExportQueue(
        SqlaCandidateRepository(bench.session), SqlaAnkiSyncRepository(bench.session),
        SqlaOccurrenceRepository(bench.session),
    )
    batch = queue.for_source(1)
    assert [card.phrase_id for card in batch.pending] == [phrase_id_of(1)]
    assert batch.exported_count == 0
