from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_role import SourceRole

if TYPE_CHECKING:
    from backend.domain.entities.source import Source
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository

_PENDING_JOB_STATUSES = [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.FAILED]


@dataclass(frozen=True)
class TopicGeneration:
    """AI step of a topic source: whether it is still needed and how its job is doing."""

    awaiting: bool = False
    status: str | None = None
    error: str | None = None


class TopicGenerationProbe:
    """Tells whether a topic still waits for its targets from AI."""

    def __init__(self, job_repo: JobRepository, topic_target_repo: TopicTargetRepository) -> None:
        self._job_repo = job_repo
        self._topic_target_repo = topic_target_repo

    def of(self, source: Source) -> TopicGeneration:
        assert source.id is not None
        if source.role is not SourceRole.TOPIC or self._topic_target_repo.has_targets(source.id):
            return TopicGeneration()
        jobs = self._job_repo.get_jobs_by_status(
            _PENDING_JOB_STATUSES, source_id=source.id, job_type=JobType.TOPIC_TARGETS,
        )
        job = jobs[0] if jobs else None
        return TopicGeneration(
            awaiting=True,
            status=job.status.value if job else None,
            error=job.error if job else None,
        )
