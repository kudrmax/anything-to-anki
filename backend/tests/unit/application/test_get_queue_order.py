"""Unit tests for GetQueueOrderUseCase."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_queue_order import GetQueueOrderUseCase
from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType


def _job(
    job_id: int,
    job_type: JobType,
    source_id: int,
    status: JobStatus = JobStatus.QUEUED,
) -> Job:
    return Job(
        id=job_id,
        job_type=job_type,
        candidate_id=100,
        source_id=source_id,
        status=status,
        error=None,
        created_at=datetime.now(tz=UTC),
        started_at=None,
    )


@pytest.mark.unit
class TestGetQueueOrderUseCase:
    def test_combines_running_and_queued_jobs(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()

        running_job = _job(1, JobType.MEANING, 10, JobStatus.RUNNING)
        queued_job1 = _job(2, JobType.MEDIA, 20)
        queued_job2 = _job(3, JobType.MEANING, 10)

        job_repo.get_jobs_by_status.side_effect = [
            [running_job],                  # running
            [queued_job1, queued_job2],      # queued with limit
            [queued_job1, queued_job2],      # queued for total count
        ]
        source_repo.get_title_map.return_value = {10: "Source A", 20: "Source B"}

        uc = GetQueueOrderUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert len(result.running) == 1
        assert result.running[0].job_id == 1
        assert result.running[0].status == "running"
        assert result.running[0].source_title == "Source A"

        assert len(result.queued) == 2
        assert result.queued[0].position == 1
        assert result.queued[1].position == 2
        assert result.total_queued == 2

    def test_empty_queues(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()
        job_repo.get_jobs_by_status.return_value = []
        source_repo.get_title_map.return_value = {}

        uc = GetQueueOrderUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert result.running == []
        assert result.queued == []
        assert result.total_queued == 0

    def test_unknown_source_gets_empty_title(self) -> None:
        job_repo = MagicMock()
        source_repo = MagicMock()

        job_repo.get_jobs_by_status.side_effect = [
            [_job(1, JobType.MEANING, 99, JobStatus.RUNNING)],
            [],
            [],
        ]
        source_repo.get_title_map.return_value = {}

        uc = GetQueueOrderUseCase(job_repo=job_repo, source_repo=source_repo)
        result = uc.execute()

        assert result.running[0].source_title == ""
