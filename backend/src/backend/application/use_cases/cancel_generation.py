from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.job_selection import JobSelection

if TYPE_CHECKING:
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.generation_kind import GenerationKind
    from backend.domain.value_objects.source_scope import SourceScope


class CancelGenerationUseCase:
    """Stops one kind of generation for every source of a set: their queued and running
    jobs are dropped, and a running job's result is discarded when it arrives."""

    def __init__(self, job_repo: JobRepository, scope_resolver: SourceScopeResolver) -> None:
        self._job_repo = job_repo
        self._scope_resolver = scope_resolver

    def execute(self, scope: SourceScope, kind: GenerationKind) -> int:
        """Returns how many jobs were cancelled."""
        return sum(
            self._job_repo.cancel(JobSelection(job_type=kind.job_type, source_id=source.id))
            for source in self._scope_resolver.reviewable_sources(scope)
            if source.id is not None
        )
