from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_reprocess_stats import (
    GetReprocessStatsUseCase,
    ReprocessStats,
)
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_use_case() -> tuple[GetReprocessStatsUseCase, dict[str, MagicMock]]:
    mocks: dict[str, MagicMock] = {
        "source_repo": MagicMock(),
        "candidate_repo": MagicMock(),
        "meaning_repo": MagicMock(),
        "media_repo": MagicMock(),
        "pronunciation_repo": MagicMock(),
    }
    use_case = GetReprocessStatsUseCase(
        source_repo=mocks["source_repo"],
        candidate_repo=mocks["candidate_repo"],
        meaning_repo=mocks["meaning_repo"],
        media_repo=mocks["media_repo"],
        pronunciation_repo=mocks["pronunciation_repo"],
    )
    return use_case, mocks


def _make_candidate(source_id: int, status: CandidateStatus) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id,
        lemma="test",
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="a test fragment",
        fragment_purity="clean",
        occurrences=1,
        status=status,
    )


@pytest.mark.unit
class TestGetReprocessStatsUseCase:
    def test_returns_counts(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = [
            _make_candidate(1, CandidateStatus.LEARN),
            _make_candidate(1, CandidateStatus.KNOWN),
            _make_candidate(1, CandidateStatus.SKIP),
            _make_candidate(1, CandidateStatus.PENDING),
        ]
        # no active enrichments
        for repo_name in ("meaning_repo", "media_repo", "pronunciation_repo"):
            mocks[repo_name].get_candidate_ids_by_status.return_value = []

        result = use_case.execute(1)

        assert isinstance(result, ReprocessStats)
        assert result.learn_count == 1
        assert result.known_count == 1
        assert result.skip_count == 1
        assert result.pending_count == 1
        assert result.has_active_jobs is False

    def test_has_active_jobs_when_meaning_running(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = MagicMock()
        mocks["candidate_repo"].get_by_source.return_value = []

        def meaning_ids_by_status(source_id: int, status: EnrichmentStatus) -> list[int]:
            if status == EnrichmentStatus.RUNNING:
                return [10]
            return []

        mocks["meaning_repo"].get_candidate_ids_by_status.side_effect = meaning_ids_by_status
        mocks["media_repo"].get_candidate_ids_by_status.return_value = []
        mocks["pronunciation_repo"].get_candidate_ids_by_status.return_value = []

        result = use_case.execute(1)

        assert result.has_active_jobs is True

    def test_not_found(self) -> None:
        use_case, mocks = _make_use_case()
        mocks["source_repo"].get_by_id.return_value = None

        with pytest.raises(SourceNotFoundError):
            use_case.execute(999)
