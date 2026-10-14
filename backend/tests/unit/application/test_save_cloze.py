from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.save_cloze import SaveClozeUseCase
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    CardDecisionLockedError,
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    InvalidClozeError,
    PhraseNotFoundError,
)
from backend.domain.services.card_decision import DecisionAction
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase

pytestmark = pytest.mark.unit

GIVE_UP = "She finally gave up smoking last year."
PHRASE_ID = 11


def _word() -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=5, lemma="give up", pos="VERB", cefr_level="B1",
        zipf_frequency=4.0, source_phrase=phrase(GIVE_UP, "gave up"),
        occurrences=1, status=CandidateStatus.PENDING,
        is_phrasal_verb=True,
    )


def _phrase(synonyms: str = "quit, stop") -> Occurrence:
    return Occurrence(
        id=PHRASE_ID, candidate_id=1, origin=OccurrenceOrigin.AUTO,
        source_phrase=phrase(GIVE_UP, "gave up"), phrase_position=None, key=None,
        fragment_score=None, shown_by=ShownBy.SELECTION,
        meaning=CandidateMeaning(
            candidate_id=1, meaning="To stop.", translation="бросить",
            synonyms=synonyms, examples=None, ipa=None, generated_at=None,
        ),
    )


class TestSaveCloze:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.occurrence_repo = MagicMock()
        self.cloze_repo = MagicMock()
        self.job_repo = MagicMock()
        self.job_repo.get_jobs_for_candidates.return_value = {}
        self.report_repo = MagicMock()
        self.report_repo.reported_candidate_ids.return_value = set()
        self.candidate_repo.get_by_id.return_value = _word()
        self.occurrence_repo.get.return_value = _phrase()
        self.decide = MagicMock()
        self.use_case = SaveClozeUseCase(
            occurrence_repo=self.occurrence_repo,
            candidate_repo=self.candidate_repo,
            cloze_repo=self.cloze_repo,
            job_repo=self.job_repo,
            report_repo=self.report_repo,
            decide_phrase=self.decide,
            builder=ClozeBuilder(),
        )

    def test_save_decides_cloze_and_stores_markup(self) -> None:
        self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.TRANSLATION, None)
        self.decide.execute.assert_called_once_with(PHRASE_ID, DecisionAction.CLOZE)
        self.cloze_repo.upsert_for_phrase.assert_called_once_with(
            PHRASE_ID, CandidateCloze(1, (3,), ClozeHintKind.TRANSLATION, None, GIVE_UP),
        )

    def test_save_on_a_sibling_of_a_decided_word_is_refused(self) -> None:
        self.decide.execute.side_effect = CardDecisionLockedError(PHRASE_ID, WordStatus.KNOWN)
        with pytest.raises(CardDecisionLockedError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, None)
        self.cloze_repo.upsert_for_phrase.assert_not_called()

    def test_save_stores_trimmed_custom_hint(self) -> None:
        self.use_case.execute(PHRASE_ID, GIVE_UP, [2, 3], ClozeHintKind.CUSTOM, "  stop doing  ")
        self.cloze_repo.upsert_for_phrase.assert_called_once_with(
            PHRASE_ID, CandidateCloze(1, (2, 3), ClozeHintKind.CUSTOM, "stop doing", GIVE_UP),
        )

    def test_save_drops_custom_text_for_other_kinds(self) -> None:
        self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, "leftover")
        stored = self.cloze_repo.upsert_for_phrase.call_args.args[1]
        assert stored.custom_hint is None

    def test_saved_candidate_stays_reported(self) -> None:
        self.report_repo.reported_candidate_ids.return_value = {1}
        dto = self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, None)
        assert dto.reported is True
        assert dto.can_cloze is True

    def test_saved_candidate_keeps_job_status(self) -> None:
        job = Job(
            id=7, job_type=JobType.MEANING, candidate_id=1, source_id=5,
            status=JobStatus.RUNNING, error=None, created_at=datetime(2026, 1, 1, tzinfo=UTC),
            started_at=None,
        )
        self.job_repo.get_jobs_for_candidates.return_value = {1: {JobType.MEANING.value: job}}
        dto = self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, None)
        assert dto.meaning is not None
        assert dto.meaning.status == "running"

    def test_save_rejects_missing_phrase(self) -> None:
        self.occurrence_repo.get.return_value = None
        with pytest.raises(PhraseNotFoundError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, None)

    def test_save_rejects_an_exported_phrase(self) -> None:
        self.occurrence_repo.get.return_value = replace(_phrase(), exported=True)
        with pytest.raises(ClozeNotAllowedError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.NONE, None)
        self.cloze_repo.upsert_for_phrase.assert_not_called()
        self.decide.execute.assert_not_called()

    def test_save_rejects_empty_indices(self) -> None:
        with pytest.raises(InvalidClozeError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [], ClozeHintKind.NONE, None)
        self.cloze_repo.upsert_for_phrase.assert_not_called()

    def test_save_rejects_out_of_range_indices(self) -> None:
        with pytest.raises(InvalidClozeError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [42], ClozeHintKind.NONE, None)

    def test_save_rejects_custom_without_text(self) -> None:
        with pytest.raises(InvalidClozeError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [3], ClozeHintKind.CUSTOM, "   ")
        self.cloze_repo.upsert_for_phrase.assert_not_called()

    def test_save_rejects_leaking_hint(self) -> None:
        self.occurrence_repo.get.return_value = _phrase(synonyms="give up, quit")
        with pytest.raises(InvalidClozeError):
            self.use_case.execute(PHRASE_ID, GIVE_UP, [2, 3], ClozeHintKind.SYNONYMS, None)
        self.cloze_repo.upsert_for_phrase.assert_not_called()
        self.decide.execute.assert_not_called()

    def test_save_rejects_markup_of_another_phrase(self) -> None:
        with pytest.raises(ClozePhraseChangedError):
            self.use_case.execute(
                1, "She finally gave up sugar.", [3], ClozeHintKind.NONE, None,
            )
        self.cloze_repo.upsert_for_phrase.assert_not_called()
        self.decide.execute.assert_not_called()

    def test_save_dedupes_and_sorts_indices(self) -> None:
        self.use_case.execute(PHRASE_ID, GIVE_UP, [3, 2, 3], ClozeHintKind.NONE, None)
        stored = self.cloze_repo.upsert_for_phrase.call_args.args[1]
        assert stored.hidden_word_indices == (2, 3)
