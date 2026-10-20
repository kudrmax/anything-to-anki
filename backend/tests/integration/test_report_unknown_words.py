"""A report's unknown words in a real database (spec §1): a word the user learns stays as
it is; a Known word goes Unknown through the Known removal; any other word goes Unknown."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.card_report_dtos import ReportCandidateRequest
from backend.application.use_cases.report_candidate import ReportCandidateUseCase
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_card_report_repository import (
    SqlaCardReportRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LEMMA = "glare"
REPORTED = 1                    # the word whose card is reported, in source 1
OTHER_SOURCE = 2
OTHER_WORD = 50                 # the lemma in source 2
THE_TARGET = 0                  # the reported phrase is the one word "glare"


class Bench:
    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(session, REPORTED, lemma=LEMMA, phrase_text=LEMMA)
        insert_source(session, OTHER_SOURCE)

    def other(self, status: str) -> None:
        insert_word(self.session, OTHER_WORD, source_id=OTHER_SOURCE, lemma=LEMMA, status=status)

    def list_known(self) -> None:
        self.session.execute(text(
            "INSERT INTO known_words (lemma, pos, created_at) VALUES (:l, NULL, '2026-01-01')"
        ), {"l": LEMMA})

    def report_unknown(self) -> None:
        self.session.commit()
        decisions = Decisions(self.session)
        recorder = SessionChangeRecorder(self.session)
        knowledge = MagicMock()
        knowledge.current.return_value = None
        ReportCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(self.session, recorder),
            occurrence_repo=SqlaOccurrenceRepository(self.session, recorder),
            source_repo=SqlaSourceRepository(self.session, recorder),
            document_repo=SqlaDocumentRepository(self.session),
            report_repo=SqlaCardReportRepository(self.session),
            knowledge=knowledge,
            effects=decisions.effects(),
            unit_of_work=SqlaUnitOfWork(self.session, decisions.scope),
        ).execute(phrase_id_of(REPORTED), ReportCandidateRequest(unknown_words=[THE_TARGET]))

    def scalar(self, sql: str) -> object:
        return self.session.execute(text(sql)).scalar_one()

    def unknown(self) -> set[str]:
        return {str(lemma) for (lemma,) in self.session.execute(
            text("SELECT lemma FROM unknown_words"),
        )}

    def known(self) -> int:
        return int(str(self.scalar("SELECT count(*) FROM known_words")))

    def status(self, word_id: int) -> str:
        return str(self.scalar(f"SELECT status FROM candidates WHERE id = {word_id}"))  # noqa: S608

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
