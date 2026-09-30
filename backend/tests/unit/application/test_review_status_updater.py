from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_status_updater import ReviewStatusUpdater
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus


def _candidate(status: CandidateStatus) -> StoredCandidate:
    return StoredCandidate(
        id=1, source_id=7, lemma="pursuit", pos="NOUN", cefr_level="B2", zipf_frequency=3.5,
        context_fragment="the pursuit of", fragment_purity="clean", occurrences=1, status=status,
    )


def _source(status: SourceStatus) -> MagicMock:
    source = MagicMock()
    source.status = status
    return source


@pytest.mark.unit
class TestReviewStatusUpdater:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.updater = ReviewStatusUpdater(
            source_repo=self.source_repo, candidate_repo=self.candidate_repo,
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
