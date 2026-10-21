"""Learn → learning: words waiting for export and words exported to Anki, in a real database."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.get_learning_words import GetLearningWordsUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_word_mark_repository import (
    SqlaWordMarkRepository,
)
from sqlalchemy import text

from tests.decision_support import NOW, Decisions
from tests.phrase_support import phrase
from tests.word_support import CREATED_AT, TEST_SECTION, bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOTE = 900
OTHER_PHRASE = 5000


class Bench:
    """The user's words over a real database."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.known = SqlaWordMarkRepository(session, SessionChangeRecorder(session))
        self.learning = SqlaLearningQuery(session)
        self.decisions = Decisions(session)

    @property
    def vocabulary(self):  # noqa: ANN201 — the request's vocabulary, read anew
        return self.decisions.request().vocabulary

    def exported_learn_word(self, word_id: int, lemma: str, note_id: int) -> None:
        insert_word(self.session, word_id, lemma=lemma, status=WordStatus.LEARN.value)
        bind(self.session, word_id, phrase_id_of(word_id), note_id=note_id)

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
    bench.known.mark_known("glare", None)

    assert bench.is_known("glare")
    assert not bench.is_learning("glare")


def test_deleting_the_source_keeps_the_exported_word_learning(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    SqlaSourceRepository(bench.session, SessionChangeRecorder(bench.session)).delete(1)
    bench.session.flush()

    assert bench.is_learning("glare")


def test_a_deleted_sources_export_turns_the_word_known_by_its_timer(bench: Bench) -> None:
    """Q13: the binding outlives its source (SET NULL); its timer still runs."""
    insert_word(bench.session, 1, lemma="glare", status=WordStatus.LEARN.value)
    bind(bench.session, 1, phrase_id_of(1), note_id=NOTE, since="2026-09-01 00:00:00")
    SqlaSourceRepository(bench.session, SessionChangeRecorder(bench.session)).delete(1)
    bench.session.flush()

    orphan = bench.session.execute(text(
        "SELECT candidate_id, phrase_id, released_at FROM anki_synced_cards"
    )).one()
    assert tuple(orphan) == (None, None, None)
    assert bench.is_known("glare")
    assert bench.vocabulary.of("glare").timer_known


def test_the_learning_list_tells_words_in_anki_from_words_waiting(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    insert_word(bench.session, 2, lemma="linger", status=WordStatus.LEARN.value)
    insert_word(bench.session, 3, lemma="wander", status=WordStatus.LEARN.value)
    bench.known.mark_known("wander", None)

    learning = GetLearningWordsUseCase(bench.vocabulary).execute()

    assert [(word.lemma, word.known_on) for word in learning.in_anki] == [
        ("glare", NOW - timedelta(days=1) + LEARNING_KNOWN_AFTER),
    ]
    assert learning.awaiting_export == ["linger"]


def test_the_learning_list_leaves_out_a_word_known_by_its_timer(bench: Bench) -> None:
    insert_word(bench.session, 1, lemma="glare", status=WordStatus.LEARN.value)
    bind(bench.session, 1, phrase_id_of(1), note_id=NOTE, since="2026-09-01 00:00:00")

    learning = GetLearningWordsUseCase(bench.vocabulary).execute()

    assert learning.in_anki == []
    assert learning.awaiting_export == []


def test_every_active_binding_is_in_anki_and_a_released_one_is_not(bench: Bench) -> None:
    bench.exported_learn_word(1, "glare", NOTE)
    bench.exported_learn_word(2, "Drift", NOTE + 1)
    insert_word(bench.session, 3, lemma="wander", status=WordStatus.LEARN.value)
    bind(bench.session, 3, phrase_id_of(3), released_at=CREATED_AT)

    assert bench.learning.in_anki() == frozenset({"glare", "drift"})


def test_a_decision_phrase_waits_for_export_though_another_phrase_was_exported(
    bench: Bench,
) -> None:
    """A word merged from cards keeps the released export record of a phrase that is not
    its decision: the decision phrase still goes to Anki."""
    insert_word(bench.session, 1, lemma="linger", status=WordStatus.LEARN.value)
    bench.session.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, choice,"
            " created_at, earned_section)"
            " VALUES (:id, 1, :phrase, 'manual', 'user', 'none', :created_at, :section)"
        ),
        {"id": OTHER_PHRASE, "phrase": dump_phrase(phrase("We linger.", "linger")),
         "created_at": CREATED_AT, "section": TEST_SECTION},
    )
    bind(bench.session, 1, OTHER_PHRASE, note_id=NOTE, released_at=CREATED_AT)

    assert bench.learning.awaiting_export() == frozenset({"linger"})
    decisions = bench.decisions.request()
    queue = ExportQueue(
        SqlaCandidateRepository(bench.session, SessionChangeRecorder(bench.session)),
        SqlaOccurrenceRepository(bench.session, SessionChangeRecorder(bench.session)),
        decisions.word_states, decisions.vocabulary,
    )
    batch = queue.for_sources([1])
    assert [card.phrase_id for card in batch.pending] == [phrase_id_of(1)]
    assert batch.exported_count == 0
