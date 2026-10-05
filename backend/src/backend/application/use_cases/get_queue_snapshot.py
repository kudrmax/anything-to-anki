from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.queue_dtos import (
    FailedByJobTypeDTO,
    FailedGroupDTO,
    FailedSourceDTO,
    JobTypeCountsDTO,
    QueueJobDTO,
    QueueSnapshotDTO,
)
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.entities.job import Job
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository

PIPELINE_ORDER: tuple[JobType, ...] = (
    JobType.VIDEO_DOWNLOAD,
    JobType.TOPIC_TARGETS,
    JobType.POLISH,
    JobType.MEANING,
    JobType.MEDIA,
    JobType.PRONUNCIATION,
    JobType.TTS,
)


class GetQueueSnapshotUseCase:
    """Counts, running jobs, the head of the line and failures — globally or for one source."""

    def __init__(self, job_repo: JobRepository, source_repo: SourceRepository) -> None:
        self._job_repo = job_repo
        self._source_repo = source_repo

    def execute(self, source_id: int | None = None, queued_limit: int = 50) -> QueueSnapshotDTO:
        summary = self._job_repo.get_queue_summary(source_id=source_id)
        counts = [
            JobTypeCountsDTO(job_type=job_type.value, **summary[job_type.value])
            for job_type in PIPELINE_ORDER
            if any(summary[job_type.value].values())
        ]
        running = self._job_repo.get_jobs_by_status([JobStatus.RUNNING], source_id=source_id)
        queued = self._job_repo.get_jobs_by_status(
            [JobStatus.QUEUED], source_id=source_id, limit=queued_limit,
        )
        failed_groups = self._job_repo.get_failed_grouped_by_error(source_id=source_id)

        source_ids = {j.source_id for j in running + queued}
        for group in failed_groups:
            source_ids.update(group.source_ids)
        titles = self._source_repo.get_title_map(sorted(source_ids)) if source_ids else {}

        def job_dto(job: Job, position: int | None) -> QueueJobDTO:
            assert job.id is not None
            return QueueJobDTO(
                job_id=job.id,
                job_type=job.job_type.value,
                source_id=job.source_id,
                source_title=titles.get(job.source_id, ""),
                status=job.status.value,
                position=position,
                candidate_id=job.candidate_id,
            )

        failed: list[FailedByJobTypeDTO] = []
        for job_type in PIPELINE_ORDER:
            groups = [
                FailedGroupDTO(
                    error_text=g.error,
                    count=g.count,
                    sources=[
                        FailedSourceDTO(
                            source_id=sid, source_title=titles.get(sid, ""),
                            count=g.source_counts[sid],
                        )
                        for sid in g.source_ids
                    ],
                )
                for g in failed_groups if g.job_type == job_type
            ]
            if groups:
                failed.append(FailedByJobTypeDTO(
                    job_type=job_type.value,
                    total_failed=sum(g.count for g in groups),
                    groups=groups,
                ))

        return QueueSnapshotDTO(
            counts=counts,
            total_queued=sum(c.queued for c in counts),
            total_running=sum(c.running for c in counts),
            total_failed=sum(c.failed for c in counts),
            running=[job_dto(j, None) for j in running],
            queued=[job_dto(j, i) for i, j in enumerate(queued, 1)],
            failed=failed,
        )
