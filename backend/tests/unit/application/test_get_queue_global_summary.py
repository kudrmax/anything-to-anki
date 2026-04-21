"""Unit tests for GetQueueGlobalSummaryUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.get_queue_global_summary import (
    GetQueueGlobalSummaryUseCase,
)
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_use_case(
    meaning_repo: MagicMock | None = None,
    media_repo: MagicMock | None = None,
    pronunciation_repo: MagicMock | None = None,
    source_repo: MagicMock | None = None,
) -> GetQueueGlobalSummaryUseCase:
    return GetQueueGlobalSummaryUseCase(
        meaning_repo=meaning_repo or MagicMock(),
        media_repo=media_repo or MagicMock(),
        pronunciation_repo=pronunciation_repo or MagicMock(),
        source_repo=source_repo or MagicMock(),
    )


@pytest.mark.unit
class TestGetQueueGlobalSummaryUseCase:
    def test_returns_zeros_when_all_repos_return_zero(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.count_by_status_global.return_value = 0
        media_repo = MagicMock()
        media_repo.count_by_status_global.return_value = 0
        pronunciation_repo = MagicMock()
        pronunciation_repo.count_by_status_global.return_value = 0

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert result.meanings.queued == 0
        assert result.meanings.running == 0
        assert result.meanings.failed == 0
        assert result.media.queued == 0
        assert result.media.running == 0
        assert result.media.failed == 0
        assert result.pronunciation.queued == 0
        assert result.pronunciation.running == 0
        assert result.pronunciation.failed == 0
        assert result.youtube_dl.queued == 0
        assert result.youtube_dl.running == 0
        assert result.youtube_dl.failed == 0
        assert result.processing.queued == 0
        assert result.processing.running == 0
        assert result.processing.failed == 0

    def test_aggregates_counts_correctly(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.count_by_status_global.side_effect = (
            lambda status, source_id=None: {
                EnrichmentStatus.QUEUED: 5,
                EnrichmentStatus.RUNNING: 2,
                EnrichmentStatus.FAILED: 3,
            }[status]
        )
        media_repo = MagicMock()
        media_repo.count_by_status_global.side_effect = (
            lambda status, source_id=None: {
                EnrichmentStatus.QUEUED: 10,
                EnrichmentStatus.RUNNING: 1,
                EnrichmentStatus.FAILED: 0,
            }[status]
        )
        pronunciation_repo = MagicMock()
        pronunciation_repo.count_by_status_global.side_effect = (
            lambda status, source_id=None: {
                EnrichmentStatus.QUEUED: 7,
                EnrichmentStatus.RUNNING: 0,
                EnrichmentStatus.FAILED: 4,
            }[status]
        )

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert result.meanings.queued == 5
        assert result.meanings.running == 2
        assert result.meanings.failed == 3
        assert result.media.queued == 10
        assert result.media.running == 1
        assert result.media.failed == 0
        assert result.pronunciation.queued == 7
        assert result.pronunciation.running == 0
        assert result.pronunciation.failed == 4

    def test_passes_source_id_to_repos(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.count_by_status_global.return_value = 0
        media_repo = MagicMock()
        media_repo.count_by_status_global.return_value = 0
        pronunciation_repo = MagicMock()
        pronunciation_repo.count_by_status_global.return_value = 0

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        use_case.execute(source_id=42)

        for status in (EnrichmentStatus.QUEUED, EnrichmentStatus.RUNNING, EnrichmentStatus.FAILED):
            meaning_repo.count_by_status_global.assert_any_call(status, source_id=42)
            media_repo.count_by_status_global.assert_any_call(status, source_id=42)
            pronunciation_repo.count_by_status_global.assert_any_call(status, source_id=42)

    def test_calls_each_repo_three_times(self) -> None:
        """Each enrichment repo must be called for QUEUED, RUNNING, FAILED."""
        meaning_repo = MagicMock()
        meaning_repo.count_by_status_global.return_value = 0
        media_repo = MagicMock()
        media_repo.count_by_status_global.return_value = 0
        pronunciation_repo = MagicMock()
        pronunciation_repo.count_by_status_global.return_value = 0

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        use_case.execute()

        assert meaning_repo.count_by_status_global.call_count == 3
        assert media_repo.count_by_status_global.call_count == 3
        assert pronunciation_repo.count_by_status_global.call_count == 3
