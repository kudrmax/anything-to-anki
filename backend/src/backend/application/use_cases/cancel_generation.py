from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.job_selection import JobSelection

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.generation_kind import GenerationKind


class CancelGenerationUseCase:
    """Stops one kind of generation for a source: its queued and running jobs are
    dropped, and a running job's result is discarded when it arrives."""

    def __init__(self, job_repo: JobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, source_id: int, kind: GenerationKind) -> int:
        """Returns how many jobs were cancelled."""
        return self._job_repo.cancel(JobSelection(job_type=kind.job_type, source_id=source_id))
