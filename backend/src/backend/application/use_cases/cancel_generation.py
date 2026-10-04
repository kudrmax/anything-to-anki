from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.generation_kind import GenerationKind


class CancelGenerationUseCase:
    """Stops one kind of generation for a source: queued jobs are dropped, running ones stop."""

    def __init__(self, job_repo: JobRepository) -> None:
        self._job_repo = job_repo

    def execute(self, source_id: int, kind: GenerationKind) -> int:
        """Returns how many jobs were cancelled."""
        return self._job_repo.delete_by_source_and_type(source_id, kind.job_type)
