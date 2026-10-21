"""A report's unknown words in a real database (spec §1): a word the user learns stays as
it is; a Known word loses Known through the Known removal and goes Unknown unless the removal
left it learned; any other word goes Unknown."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.card_report_dtos import ReportCandidateRequest
from backend.application.use_cases.report_candidate import ReportCandidateUseCase
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_report_repository import (
    SqlaCardReportRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from tests.decision_support import NOW, Decisions
from tests.integration.conftest import insert_source
from tests.word_marks_support import insert_known, known_rows, unknown_lemmas
from tests.word_support import bind, decision_status_of, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LEMMA = "glare"
REPORTED = 1                    # the word whose card is reported, in source 1
OTHER_SOURCE = 2
OTHER_WORD = 50                 # the lemma in source 2
THE_TARGET = 0                  # the reported phrase is the one word "glare"
THIRD_SOURCE = 3
THIRD_WORD = 60                 # the lemma in source 3
FRESH = (NOW - LEARNING_KNOWN_AFTER + timedelta(days=1)).replace(tzinfo=None).isoformat(sep=" ")
DUE = (NOW - LEARNING_KNOWN_AFTER).replace(tzinfo=None).isoformat(sep=" ")
DUE_ORPHAN, FRESH_ORPHAN = 77, 78


class Bench:
    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, REPORTED, lemma=LEMMA, phrase_text=LEMMA)
        insert_source(session, OTHER_SOURCE)

    def other(self, status: str) -> None:
        insert_word(self.session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA, status=status)

    def third(self, status: str) -> None:
        insert_source(self.session, THIRD_SOURCE)
        insert_word(self.session, THIRD_WORD, source_id=THIRD_SOURCE, lemma=LEMMA, status=status)

    def orphan(self, note_id: int, since: str) -> None:
        """An active binding whose card is gone."""
        self.session.execute(text(
            "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id, lemma, pos,"
            " note_kind, card_choice, learning_since)"
            " VALUES (NULL, NULL, :note, :lemma, 'NOUN', 'learn', 'learn', :since)"
        ), {"note": note_id, "lemma": LEMMA, "since": since})

    def orphan_active(self, note_id: int) -> bool:
        return self.session.execute(text(
            "SELECT released_at IS NULL FROM anki_synced_cards WHERE anki_note_id = :note"
        ), {"note": note_id}).scalar_one() == 1

    def list_known(self) -> None:
        insert_known(self.session, LEMMA)

    def lock(self, source_id: int) -> None:
        """Another operation holds the source, as a rebuild of it would."""
        assert SqlaSourceOperationLock(self.session).acquire(
            source_id, SourceOperationKind.UPDATE,
        )

    def report_unknown(self) -> None:
        self.session.commit()
        decisions = Decisions(self.session, lock=SqlaSourceOperationLock(self.session))
        recorder = SessionChangeRecorder(self.session)
        knowledge = MagicMock()
        knowledge.current.return_value = None
        ReportCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(self.session, recorder),
            occurrence_repo=SqlaOccurrenceRepository(self.session, recorder),
            source_repo=SqlaSourceRepository(self.session, recorder),
            document_repo=SqlaDocumentRepository(self.session),
            report_repo=SqlaCardReportRepository(self.session, recorder),
            knowledge=knowledge,
            effects=decisions.effects(),
            unit_of_work=SqlaUnitOfWork(self.session, decisions.scope),
        ).execute(phrase_id_of(REPORTED), ReportCandidateRequest(unknown_words=[THE_TARGET]))

    def scalar(self, sql: str) -> object:
        return self.session.execute(text(sql)).scalar_one()

    def unknown(self) -> set[str]:
        return unknown_lemmas(self.session)

    def known(self) -> int:
        return len(known_rows(self.session))

    def status(self, word_id: int) -> str:
        return decision_status_of(self.session, word_id)

    def choice(self, word_id: int) -> str:
        return str(self.scalar(
            f"SELECT choice FROM phrases WHERE id = {phrase_id_of(word_id)}",  # noqa: S608
        ))

    def active_bindings(self) -> int:
        return int(str(self.scalar(
            "SELECT count(*) FROM anki_synced_cards WHERE released_at IS NULL",
        )))


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


def test_a_word_learned_in_another_source_stays_as_it_is(bench: Bench) -> None:
    bench.other("learn")

    bench.report_unknown()

    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == ("learn", "learn")
    assert bench.unknown() == set()


def test_a_word_in_anki_stays_as_it_is(bench: Bench) -> None:
    bench.other("learn")
    bind(bench.session, OTHER_WORD, phrase_id_of(OTHER_WORD), lemma=LEMMA)

    bench.report_unknown()

    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == ("learning", "learn")
    assert bench.active_bindings() == 1
    assert bench.unknown() == set()


@pytest.mark.parametrize(("exported", "status"), [(False, "learn"), (True, "learning")])
def test_a_learned_word_stays_as_it_is_while_another_source_of_it_is_busy(
    bench: Bench, exported: bool, status: str,
) -> None:
    """Nothing is written for a learned word, so no lock is waited for nor refused."""
    bench.other("learn")
    if exported:
        bind(bench.session, OTHER_WORD, phrase_id_of(OTHER_WORD), lemma=LEMMA)
    bench.lock(OTHER_SOURCE)

    bench.report_unknown()

    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == (status, "learn")
    assert bench.active_bindings() == int(exported)
    assert bench.unknown() == set()
    assert bench.known() == 0


def test_a_known_word_goes_unknown_through_the_known_removal(bench: Bench) -> None:
    bench.list_known()
    bench.other("known")

    bench.report_unknown()

    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == ("pending", "none")
    assert bench.known() == 0
    assert bench.unknown() == {LEMMA}


def test_a_new_word_goes_unknown(bench: Bench) -> None:
    bench.report_unknown()

    assert bench.unknown() == {LEMMA}
    assert bench.status(REPORTED) == "pending"


def test_a_word_known_by_its_timer_with_a_learn_left_loses_known_and_is_not_marked(
    bench: Bench,
) -> None:
    """The removal keeps the Learn not exported yet, so the word is still learned."""
    bench.other("learn")
    bind(bench.session, OTHER_WORD, phrase_id_of(OTHER_WORD), lemma=LEMMA, since=DUE)
    bench.third("learn")

    bench.report_unknown()

    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == ("pending", "none")
    assert bench.active_bindings() == 0
    assert (bench.status(THIRD_WORD), bench.choice(THIRD_WORD)) == ("learn", "learn")
    assert bench.unknown() == set()


def test_a_listed_word_with_a_note_still_learning_loses_known_and_is_not_marked(
    bench: Bench,
) -> None:
    """The due orphan goes with Known; the one whose timer runs keeps the word learning."""
    bench.list_known()
    bench.other("known")
    bench.orphan(DUE_ORPHAN, DUE)
    bench.orphan(FRESH_ORPHAN, FRESH)

    bench.report_unknown()

    assert bench.known() == 0
    assert (bench.status(OTHER_WORD), bench.choice(OTHER_WORD)) == ("pending", "none")
    assert not bench.orphan_active(DUE_ORPHAN)
    assert bench.orphan_active(FRESH_ORPHAN)
    assert bench.unknown() == set()
