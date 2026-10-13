import itertools
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_status_updater import ReviewStatusUpdater
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.phrase_words import PhraseWord, PhraseWords
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import candidate_sorter


def _candidate(status: CandidateStatus, *, other_new_words: int = 0) -> StoredCandidate:
    return StoredCandidate(
        id=next(_IDS), source_id=7, lemma="pursuit", pos="NOUN", cefr_level="B2",
        zipf_frequency=3.5, context_fragment="the pursuit of", occurrences=1, status=status,
        phrase_words=PhraseWords(
            phrase="the pursuit of",
            words=tuple(PhraseWord(f"strange{i}", rare=True) for i in range(other_new_words)),
        ),
    )


_IDS = itertools.count(1)


def _source(status: SourceStatus) -> MagicMock:
    source = MagicMock()
    source.id = 7
    source.status = status
    return source


@pytest.mark.unit
class TestReviewStatusUpdater:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        settings_repo = MagicMock()
        settings_repo.get.return_value = None
        self.updater = ReviewStatusUpdater(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            candidate_sorter=candidate_sorter(settings_repo),
        )

    def test_saves_the_derived_status_when_it_changes(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        self.candidate_repo.get_by_source.return_value = [
            _candidate(CandidateStatus.LEARN), _candidate(CandidateStatus.PENDING),
        ]
        self.updater.refresh(7)
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.PARTIALLY_REVIEWED)

    def test_does_not_write_when_the_status_is_unchanged(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.REVIEWED)
        self.candidate_repo.get_by_source.return_value = [_candidate(CandidateStatus.KNOWN)]
        self.updater.refresh(7)
        self.source_repo.update_status.assert_not_called()

    def test_ignores_a_missing_source(self) -> None:
        self.source_repo.get_by_id.return_value = None
        self.updater.refresh(7)
        self.source_repo.update_status.assert_not_called()

    def test_cards_with_other_new_words_do_not_hold_the_source(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.PARTIALLY_REVIEWED)
        self.candidate_repo.get_by_source.return_value = [
            _candidate(CandidateStatus.LEARN),
            _candidate(CandidateStatus.PENDING, other_new_words=1),
        ]
        self.updater.refresh(7)
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.REVIEWED)

    def test_refresh_all_goes_through_every_source(self) -> None:
        self.source_repo.list_all.return_value = [_source(SourceStatus.DONE)]
        self.candidate_repo.get_by_source.return_value = [_candidate(CandidateStatus.LEARN)]
        self.updater.refresh_all()
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.REVIEWED)
