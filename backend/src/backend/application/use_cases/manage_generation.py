from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.generation_dtos import GenerationJobDTO, GenerationQueueDTO
from backend.domain.exceptions import GenerationAlreadyRunningError, NoActiveCandidatesError
from backend.domain.value_objects.generation_job_status import GenerationJobStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.entities.generation_job import GenerationJob
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.generation_job_repository import GenerationJobRepository

BATCH_SIZE = 15


class StartGenerationUseCase:
    """Creates N GenerationJob-s (one per batch) for background processing."""

    def __init__(
        self,
        job_repo: GenerationJobRepository,
        meaning_repo: CandidateMeaningRepository,
    ) -> None:
        self._job_repo = job_repo
        self._meaning_repo = meaning_repo

    def execute(self, source_id: int | None) -> GenerationQueueDTO:
        # Check no RUNNING or PENDING job exists
        running = self._job_repo.get_running()
        if running is not None:
            raise GenerationAlreadyRunningError()
        pending = self._job_repo.get_pending()
        if pending:
            raise GenerationAlreadyRunningError()

        # Get all active candidates without meaning
        candidate_ids = self._meaning_repo.get_candidate_ids_without_meaning(
            source_id=source_id, only_active=True,
        )
        if not candidate_ids:
            raise NoActiveCandidatesError()

        # Split into batches
        batches = [
            candidate_ids[i:i + BATCH_SIZE] for i in range(0, len(candidate_ids), BATCH_SIZE)
        ]

        from backend.domain.entities.generation_job import GenerationJob

        # Create all jobs
        created_jobs: list[GenerationJob] = []
        for batch_ids in batches:
            job = GenerationJob(
                source_id=source_id,
                status=GenerationJobStatus.PENDING,
                total_candidates=len(batch_ids),
                candidate_ids=batch_ids,
            )
            job = self._job_repo.create(job)
            created_jobs.append(job)
            logger.info(
                "Generation job %d created: source_id=%s, batch_size=%d",
                job.id, source_id, len(batch_ids)
            )

        # Return queue view
        return GenerationQueueDTO(
            running_job=None,
            pending_jobs=[_to_dto(j) for j in created_jobs],
            total_pending_count=len(candidate_ids),
        )


class StopGenerationUseCase:
    """Stops the running job and cancels all pending jobs for that source."""

    def __init__(self, job_repo: GenerationJobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, job_id: int) -> None:
        job = self._job_repo.get_by_id(job_id)
        if job is None:
            return
        if job.status == GenerationJobStatus.RUNNING:
            job.status = GenerationJobStatus.PAUSED
            self._job_repo.update(job)
        # Cancel all pending jobs for the same source
        self._job_repo.cancel_pending_for_source(job.source_id)
        logger.info("Generation job %d paused, pending jobs cancelled", job_id)


class GetGenerationStatusUseCase:
    """Returns the complete queue state: running job + pending jobs."""

    def __init__(self, job_repo: GenerationJobRepository) -> None:
        self._job_repo = job_repo

    def execute(self) -> GenerationQueueDTO | None:
        running = self._job_repo.get_running()
        pending = self._job_repo.get_pending()
        if running is None and not pending:
            return None
        total_pending = sum(j.total_candidates for j in pending)
        return GenerationQueueDTO(
            running_job=_to_dto(running) if running else None,
            pending_jobs=[_to_dto(j) for j in pending],
            total_pending_count=total_pending,
        )


def _to_dto(job: GenerationJob) -> GenerationJobDTO:
    return GenerationJobDTO(
        id=job.id,  # type: ignore[arg-type]
        source_id=job.source_id,
        status=job.status.value,
        total_candidates=job.total_candidates,
        processed_candidates=job.processed_candidates,
        failed_candidates=job.failed_candidates,
        skipped_candidates=job.skipped_candidates,
        candidate_ids=job.candidate_ids,
        created_at=job.created_at,
    )
