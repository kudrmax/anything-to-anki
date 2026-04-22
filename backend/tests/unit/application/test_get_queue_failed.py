"""Unit tests for GetQueueFailedUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_queue_failed import GetQueueFailedUseCase


@pytest.mark.unit
class TestGetQueueFailedUseCase:
    def test_empty_returns_empty_types(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()
        job_repo.get_failed_grouped_by_error.return_value = []

        uc = GetQueueFailedUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert result.types == []

    def test_groups_by_job_type(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()

        job_repo.get_failed_grouped_by_error.return_value = [
            {
                "job_type": "meaning",
                "error": "API timeout",
                "count": 3,
                "source_ids": [1, 2],
                "candidate_ids": [10, 20, 30],
            },
            {
                "job_type": "media",
                "error": "File not found",
                "count": 1,
                "source_ids": [1],
                "candidate_ids": [40],
            },
        ]
        source_repo.get_title_map.return_value = {1: "Source A", 2: "Source B"}

        uc = GetQueueFailedUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert len(result.types) == 2
        meaning_type = next(t for t in result.types if t.job_type == "meaning")
        assert meaning_type.total_failed == 3
        assert len(meaning_type.groups) == 1
        assert meaning_type.groups[0].error_text == "API timeout"

    def test_passes_source_id_filter(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()
        job_repo.get_failed_grouped_by_error.return_value = []

        uc = GetQueueFailedUseCase(job_repo=job_repo, source_repo=source_repo)
        uc.execute(source_id=42)

        job_repo.get_failed_grouped_by_error.assert_called_once_with(source_id=42)

    def test_candidate_ids_passed_through(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()
        job_repo.get_failed_grouped_by_error.return_value = [
            {
                "job_type": "meaning",
                "error": "err",
                "count": 2,
                "source_ids": [1],
                "candidate_ids": [10, 20],
            },
        ]
        source_repo.get_title_map.return_value = {1: "S"}

        uc = GetQueueFailedUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert result.types[0].groups[0].candidate_ids == [10, 20]
