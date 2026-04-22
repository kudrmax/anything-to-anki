"""Unit tests for GetQueueGlobalSummaryUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_queue_global_summary import (
    GetQueueGlobalSummaryUseCase,
)


@pytest.mark.unit
class TestGetQueueGlobalSummaryUseCase:
    def test_returns_summary_from_job_repo(self) -> None:
        job_repo = MagicMock()
        job_repo.get_queue_summary.return_value = {
            "meaning": {"queued": 5, "running": 1, "failed": 2},
            "media": {"queued": 0, "running": 0, "failed": 0},
            "pronunciation": {"queued": 3, "running": 0, "failed": 0},
            "video_download": {"queued": 0, "running": 0, "failed": 0},
        }

        uc = GetQueueGlobalSummaryUseCase(job_repo=job_repo)
        result = uc.execute()

        assert result.meaning.queued == 5
        assert result.meaning.running == 1
        assert result.meaning.failed == 2
        assert result.pronunciation.queued == 3
        job_repo.get_queue_summary.assert_called_once_with(source_id=None)

    def test_passes_source_id_filter(self) -> None:
        job_repo = MagicMock()
        job_repo.get_queue_summary.return_value = {
            "meaning": {"queued": 1, "running": 0, "failed": 0},
            "media": {"queued": 0, "running": 0, "failed": 0},
            "pronunciation": {"queued": 0, "running": 0, "failed": 0},
            "video_download": {"queued": 0, "running": 0, "failed": 0},
        }

        uc = GetQueueGlobalSummaryUseCase(job_repo=job_repo)
        uc.execute(source_id=42)

        job_repo.get_queue_summary.assert_called_once_with(source_id=42)

    def test_missing_job_type_returns_zeros(self) -> None:
        job_repo = MagicMock()
        job_repo.get_queue_summary.return_value = {
            "meaning": {"queued": 1, "running": 0, "failed": 0},
        }

        uc = GetQueueGlobalSummaryUseCase(job_repo=job_repo)
        result = uc.execute()

        assert result.meaning.queued == 1
        assert result.media.queued == 0
        assert result.pronunciation.queued == 0
        assert result.video_download.queued == 0
