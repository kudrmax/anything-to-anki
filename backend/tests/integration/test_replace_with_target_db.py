"""Replace with target: the word's dictionary form, as a new phrase, takes the card's place."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.replace_with_target import ReplaceWithTargetUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.application.utils.phrase_replacement import PhraseReplacement
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.services.export_readiness import missing_parts
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import text

from tests.candidate_sorter_support import section_stamper
from tests.card_support import card_views
from tests.decision_support import Decisions
from tests.lock_support import free_lock
from tests.phrase_support import phrase
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

WORD = 1
CARD = phrase_id_of(WORD)
LEMMA = "give up"


def _read(text: str, spans: list[tuple[int, int]]) -> Phrase:
    whole = phrase(text)
    return whole.with_target(tuple(
        i for i, word in enumerate(whole.words)
        if any(word.start < end and start < word.end for start, end in spans)
    ))


class Bench:
    """Phrasal verb `give up` of source 1 whose selection card is phrase CARD."""

    def __init__(self, session: Session) -> None:
        self.session = session
        insert_word(
            session, WORD, lemma=LEMMA, pos="VERB", phrase_text="He gave up the fight.",
        )
        session.commit()
        self.occurrences = SqlaOccurrenceRepository(session, SessionChangeRecorder(session))
        reader = MagicMock()
        reader.read.side_effect = _read
        decisions = Decisions(session)
        self.decisions = decisions
        self.use_case = ReplaceWithTargetUseCase(
            replacement=PhraseReplacement(
                occurrence_repo=self.occurrences,
                candidate_repo=SqlaCandidateRepository(session, SessionChangeRecorder(session)),
                stamper=section_stamper(SqlaSettingsRepository(
                    session, SessionChangeRecorder(session),
                )),
                job_repo=SqlaJobRepository(session, SessionChangeRecorder(session)),
                lock=free_lock(),
                word_states=decisions.word_states,
                vocabulary=decisions.vocabulary,
                effects=decisions.effects(),
            ),
            phrase_reader=reader,
            card_views=card_views(session),
            unit_of_work=SqlaUnitOfWork(session, decisions.scope),
        )

    def replace(self) -> Occurrence:
        """The target phrase made, the newest phrase of the word."""
        self.use_case.execute(CARD)
        made = self.occurrences.of_word(WORD)[-1]
        assert made.origin is OccurrenceOrigin.EXAMPLE
        return made

    def decide(self, choice: str) -> None:
        self.session.execute(text("UPDATE phrases SET choice = :c WHERE id = :id"),
                             {"c": choice, "id": CARD})
        self.session.commit()

    def give_meaning_and_audio(self) -> None:
        SqlaCandidateMeaningRepository(
            self.session, SessionChangeRecorder(self.session),
        ).upsert_for_phrase(CARD, CandidateMeaning(
            candidate_id=WORD, meaning="to stop trying", translation=None, synonyms=None,
            examples=None, ipa=None, generated_at=None,
        ))
        SqlaCandidateTTSRepository(
            self.session, SessionChangeRecorder(self.session),
        ).upsert_for_phrase(CARD, CandidateTTS(
            candidate_id=WORD, audio_path="/media/1/tts.mp3", generated_at=None,
        ))
        self.session.commit()

    def export_queue(self) -> ExportQueue:
        decisions = self.decisions.request()
        return ExportQueue(
            SqlaCandidateRepository(self.session, SessionChangeRecorder(self.session)),
            self.occurrences,
            decisions.word_states,
            decisions.vocabulary,
        )


@pytest.fixture
def bench(db_session: Session, source_id: int) -> Bench:
    del source_id
    return Bench(db_session)


def test_the_dictionary_form_is_the_whole_phrase_and_its_target(bench: Bench) -> None:
    made = bench.replace()

    assert made.source_phrase.text == LEMMA
    assert made.source_phrase.target_text() == LEMMA
    assert made.shown_by is ShownBy.USER
    assert made.replaces_selection
    replaced = bench.occurrences.get(CARD)
    assert replaced is not None
    assert replaced.shown_by is None


def test_the_answer_is_the_new_card_with_its_meaning_queued(bench: Bench) -> None:
    result = bench.use_case.execute(CARD)

    assert result.phrase_id != CARD
    assert result.phrase.text == LEMMA
    assert result.meaning is not None
    assert (result.meaning.meaning, result.meaning.status) == (None, "queued")
    jobs = SqlaJobRepository(
        bench.session, SessionChangeRecorder(bench.session),
    ).get_jobs_by_status([JobStatus.QUEUED])
    assert [(j.job_type, j.phrase_id) for j in jobs] == [(JobType.MEANING, result.phrase_id)]


def test_polish_leaves_the_target_alone_and_the_card_shows_no_polish(bench: Bench) -> None:
    made = bench.replace()

    assert made.polished_phrase is not None
    assert made.polished_phrase.text == LEMMA
    assert made.id is not None
    assert bench.use_case.execute(made.id).polished_phrase is None


@pytest.mark.parametrize("choice", ["learn", "known"])
def test_the_decision_moves_to_the_target(bench: Bench, choice: str) -> None:
    bench.decide(choice)

    made = bench.replace()

    assert made.id is not None
    assert bench.session.execute(
        text("SELECT id, choice FROM phrases WHERE id IN (:a, :b) ORDER BY id"),
        {"a": CARD, "b": made.id},
    ).all() == [(CARD, "none"), (made.id, choice)]


def test_export_waits_for_the_targets_own_meaning_and_speech(bench: Bench) -> None:
    bench.decide("learn")
    bench.give_meaning_and_audio()

    made = bench.replace()

    [card] = bench.export_queue().for_sources([1]).pending
    assert card.phrase.id == made.id
    assert [p.value for p in missing_parts(card.phrase)] == ["meaning", "audio"]


def test_an_unknown_phrase_is_not_found(bench: Bench) -> None:
    with pytest.raises(PhraseNotFoundError):
        bench.use_case.execute(999)
