"""Unit tests for EnqueuePronunciationDownloadUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_pronunciation_download import (
    EnqueuePronunciationDownloadUseCase,
)
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus


def _make_candidate(*, id_: int) -> StoredCandidate:
    return StoredCandidate(
        id=id_,
        source_id=1,
        lemma="word",
        pos="NOUN",
        cefr_level=None,
        zipf_frequency=4.0,
        context_fragment="some fragment",
        fragment_purity="clean",
        occurrences=1,
        surface_form=None,
        is_phrasal_verb=False,
        status=CandidateStatus.PENDING,
    )


def _make_use_case(
    pronunciation_repo: MagicMock,
    candidate_repo: MagicMock | None = None,
) -> EnqueuePronunciationDownloadUseCase:
    settings_repo = MagicMock()
    settings_repo.get.return_value = None
    return EnqueuePronunciationDownloadUseCase(
        pronunciation_repo=pronunciation_repo,
        candidate_repo=candidate_repo or MagicMock(),
        settings_repo=settings_repo,
        job_repo=MagicMock(),
    )


@pytest.mark.unit
class TestEnqueuePronunciationDownload:
    def test_enqueues_eligible_candidates(self) -> None:
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_eligible_candidate_ids.return_value = [10, 20, 30]
        candidate_repo = MagicMock()
        candidate_repo.get_by_ids.return_value = [
            _make_candidate(id_=10),
            _make_candidate(id_=20),
            _make_candidate(id_=30),
        ]
        use_case = _make_use_case(pronunciation_repo, candidate_repo)

        result = use_case.execute(source_id=1)

        assert result == [10, 20, 30]
        pronunciation_repo.get_eligible_candidate_ids.assert_called_once_with(1)
        # Jobs created via job_repo.create_bulk instead of mark_queued_bulk

    def test_returns_empty_when_none_eligible(self) -> None:
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_eligible_candidate_ids.return_value = []
        use_case = _make_use_case(pronunciation_repo)

        result = use_case.execute(source_id=1)

        assert result == []
        # mark_queued_bulk removed — jobs created via job_repo.create_bulk instead
