from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.utils.card_views import CardViews
from backend.application.utils.review_cards import ReviewCards
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.job import Job
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import candidate_sorter
from tests.card_support import PhraseWordStates, occurrence, word
from tests.vocabulary_support import user_vocabulary

SOURCE_ID = 10  # the source of `word`


@pytest.mark.unit
class TestGetCandidatesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.occurrence_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.job_repo = MagicMock()
        self.job_repo.get_jobs_for_phrases.return_value = {}
        self.job_repo.get_jobs_for_candidates.return_value = {}
        self.report_repo = MagicMock()
        self.report_repo.reported_phrase_ids.return_value = set()
        self.lock = MagicMock()
        self.lock.operations.return_value = {}
        self.use_case = GetCandidatesUseCase(
            source_repo=self.source_repo,
            card_views=CardViews(
                review_cards=ReviewCards(
                    self.candidate_repo, self.occurrence_repo,
                    PhraseWordStates(
                        lambda: self.candidate_repo.get_by_source.return_value,
                        lambda word_id: self.occurrence_repo.shown_by_word.return_value.get(
                            word_id, [],
                        ),
                    ),
                    user_vocabulary(),
                ),
                candidate_sorter=candidate_sorter(self.settings_repo),
                job_repo=self.job_repo,
                report_repo=self.report_repo,
                scope_resolver=SourceScopeResolver(self.source_repo, MagicMock()),
                source_repo=self.source_repo,
                lock=self.lock,
            ),
        )
        self.source_repo.get_by_id.return_value = Source(id=SOURCE_ID, status=SourceStatus.DONE)
        self.candidate_repo.get_by_source.return_value = [word(1, "test")]

    def test_every_shown_phrase_of_a_word_is_a_card(self) -> None:
        self.occurrence_repo.shown_by_word.return_value = {
            1: [occurrence(1, 1), occurrence(2, 1)],
        }
        result = self.use_case.execute(SOURCE_ID)
        assert [(c.phrase_id, c.word_id, c.lemma) for c in result] == [
            (1, 1, "test"), (2, 1, "test"),
        ]

    def test_forbids_new_markup_for_a_cloze_in_anki(self) -> None:
        self.occurrence_repo.shown_by_word.return_value = {
            1: [occurrence(1, 1, exported=True, decision_kind=DecisionKind.CLOZE)],
        }
        assert self.use_case.execute(SOURCE_ID)[0].can_edit_cloze is False

    def test_source_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)

    def test_dto_has_queued_status_when_the_phrase_has_a_job(self) -> None:
        self.occurrence_repo.shown_by_word.return_value = {1: [occurrence(1, 1)]}
        self.job_repo.get_jobs_for_phrases.return_value = {1: {"meaning": Job(
            id=100, job_type=JobType.MEANING, candidate_id=1, source_id=1,
            status=JobStatus.QUEUED, error=None, created_at=datetime(2025, 1, 1, tzinfo=UTC),
            started_at=None, phrase_id=1,
        )}}
        [result] = self.use_case.execute(SOURCE_ID)
        assert result.meaning is not None
        assert result.meaning.status == "queued"

    def test_dto_has_done_status_when_no_job(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        self.occurrence_repo.shown_by_word.return_value = {1: [occurrence(1, 1, meaning=meaning)]}
        [result] = self.use_case.execute(SOURCE_ID)
        assert result.meaning is not None
        assert result.meaning.status == "done"
