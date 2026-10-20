"""Every write of a phrase's text stamps the section of the text the card shows after it."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.application.utils.generation_targets import GenerationCard, PolishTarget
from backend.application.utils.job_phrases import JobPhrases
from backend.application.utils.requested_cards import RequestedCards
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.infrastructure.persistence.models import PhraseModel
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy import text

from tests.candidate_sorter_support import section_stamper
from tests.phrase_support import phrase
from tests.source_rebuild_support import LINES, Bench, at, word

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LEMMA = "zephyr"
LINE = 1
SOURCE_TEXT = "a zephyr"
NEW_WORD = "quill"
BOUNDARY_NEW_WORDS = ("back",)
POLISHED_TEXT = "a zephyr quill"
POLISH_CONFIG = PromptsConfig(
    generate_meaning_user_template="",
    generate_meaning_system="",
    generate_topic_targets_user_template="",
    generate_topic_targets_system="",
    polish_phrase_user_template="{phrase}",
    polish_phrase_system="Easy for {cefr_level}.",
)


def _read_for(text_: str, lemma: str) -> Phrase:
    found = phrase(text_, lemma, new=(NEW_WORD,))
    if not target_by_lemma(found.words, text_, lemma):
        raise TargetNotInPhraseError()
    return found


class Fixture:
    """The word "zephyr" with the Ready phrase "a zephyr" in a real database."""

    def __init__(self, session: Session) -> None:
        self.bench = Bench(session)
        self.session = session
        self.bench.processed(word(LEMMA, at(LINE, text=SOURCE_TEXT)))
        self.phrase_id = self.bench.phrase_on(LEMMA, LINE).id
        assert self.stored() == CandidateSection.READY.value
        self.reader = MagicMock()
        self.reader.read_for.side_effect = _read_for
        self.reader.read.side_effect = lambda text_, _spans: phrase(
            text_, new=BOUNDARY_NEW_WORDS,
        )
        self.stamper = section_stamper(SqlaSettingsRepository(session))
        self.rewrite = RewritePhrase(self.reader, self.bench.occurrences, self.stamper)

    def stored(self) -> str | None:
        self.session.expire_all()
        found = self.session.get(PhraseModel, self.phrase_id)
        assert found is not None
        return found.earned_section

    def force(self, section: CandidateSection) -> None:
        self.session.execute(
            text("UPDATE phrases SET earned_section = :s"), {"s": section.value},
        )
        self.session.expire_all()

    def edit(self, new_text: str) -> None:
        EditCardPhraseUseCase(
            self.bench.occurrences, self.bench.candidates, self.rewrite, self.bench.lock,
            MagicMock(),
        ).execute(self.phrase_id, new_text)

    def polish(self, answer: str) -> None:
        ai_service = MagicMock()
        ai_service.polish_phrases_batch.return_value = [PolishedPhrase(1, answer)]
        job_phrases = JobPhrases(
            self.bench.candidates, self.bench.occurrences,
            SqlaWordStateRepository(self.session), self.bench.vocabulary,
        )
        revision = self.bench.occurrences.get(self.phrase_id)
        assert revision is not None
        PhrasePolishUseCase(
            job_phrases=job_phrases,
            occurrence_repo=self.bench.occurrences,
            source_repo=self.bench.sources,
            document_repo=SqlaDocumentRepository(self.session),
            settings_repo=MagicMock(get=MagicMock(return_value="B1")),
            enrichment_reset=MagicMock(),
            ai_service=ai_service,
            prompts_config=POLISH_CONFIG,
            rewrite_phrase=self.rewrite,
            stamper=self.stamper,
            unit_of_work=MagicMock(),
        ).execute_batch([PhraseRef(self.phrase_id, revision.revision)])

    def revert(self, *, reverted: bool) -> None:
        RevertPhrasePolishUseCase(
            self.bench.occurrences, self.bench.candidates, MagicMock(), self.bench.lock,
            self.stamper,
            MagicMock(),
        ).execute(self.phrase_id, reverted=reverted)

    def enqueue_polish(self) -> None:
        EnqueuePhrasePolishUseCase(
            RequestedCards(self.bench.candidates, self.bench.occurrences, self.bench.lock),
            self.bench.occurrences, self.bench.sources, self.bench.jobs, self.stamper,
            MagicMock(),
        ).execute(self.phrase_id)

    def discard_polish(self) -> None:
        occurrence = self.bench.occurrences.get(self.phrase_id)
        found = self.bench.candidates.get_by_id(occurrence.candidate_id if occurrence else 0)
        assert occurrence is not None and found is not None
        PolishTarget(self.bench.occurrences, self.stamper).discard(
            GenerationCard(found, occurrence, in_play=True),
        )

    def set_boundary(self) -> None:
        SetPhraseBoundaryUseCase(
            self.bench.occurrences, self.bench.candidates,
            SqlaDocumentRepository(self.session), self.reader, self.bench.lock, self.stamper,
            MagicMock(),
        ).execute(self.phrase_id, SelectionDTO(
            start_block=0, start_line=LINE, start_char=0,
            end_block=0, end_line=LINE, end_char=len(LINES[LINE]),
        ))


@pytest.fixture
def fx(db_session: Session) -> Fixture:
    return Fixture(db_session)


def test_a_finished_polish_restamps(fx: Fixture) -> None:
    fx.polish(f"a **{LEMMA}** {NEW_WORD}")

    assert fx.stored() == CandidateSection.EXTRA.value


def test_a_polish_that_lost_the_target_restamps(fx: Fixture) -> None:
    fx.force(CandidateSection.EXTRA)

    fx.polish("a different phrase")

    assert fx.stored() == CandidateSection.READY.value, "the source phrase stays, so its section"


def test_reverting_and_unreverting_a_polish_restamp(fx: Fixture) -> None:
    fx.polish(f"a {LEMMA} {NEW_WORD}")

    fx.revert(reverted=True)
    assert fx.stored() == CandidateSection.READY.value

    fx.revert(reverted=False)
    assert fx.stored() == CandidateSection.EXTRA.value


def test_a_new_polish_restamps_the_reset_text(fx: Fixture) -> None:
    fx.polish(f"a {LEMMA} {NEW_WORD}")
    assert fx.stored() == CandidateSection.EXTRA.value

    fx.enqueue_polish()

    assert fx.stored() == CandidateSection.READY.value


def test_discarding_polish_for_regeneration_restamps(fx: Fixture) -> None:
    fx.polish(f"a {LEMMA} {NEW_WORD}")
    assert fx.stored() == CandidateSection.EXTRA.value

    fx.discard_polish()

    assert fx.stored() == CandidateSection.READY.value


def test_a_hand_edit_restamps(fx: Fixture) -> None:
    fx.edit(f"a {LEMMA} {NEW_WORD}")

    assert fx.stored() == CandidateSection.EXTRA.value


def test_a_boundary_restamps(fx: Fixture) -> None:
    fx.set_boundary()

    assert fx.stored() == CandidateSection.EXTRA.value
