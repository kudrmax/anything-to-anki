from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.job_selection import JobSelection

if TYPE_CHECKING:
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.generation_stops import GenerationStops
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.generation_kind import GenerationKind
    from backend.domain.value_objects.source_scope import SourceScope


class CancelGenerationUseCase:
    """Stops one kind of generation for every source of a set: their queued and running
    jobs are dropped, a running job's result is discarded when it arrives, and a run still
    queueing that kind for them queues nothing more."""

    def __init__(
        self,
        job_repo: JobRepository,
        scope_resolver: SourceScopeResolver,
        unit_of_work: UnitOfWork,
        stops: GenerationStops,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._job_repo = job_repo
        self._scope_resolver = scope_resolver
        self._stops = stops

    def execute(self, scope: SourceScope, kind: GenerationKind) -> int:
        """Returns how many jobs were cancelled."""
        with self._unit_of_work.write():
            source_ids = [
                source.id for source in self._scope_resolver.reviewable_sources(scope)
                if source.id is not None
            ]
            for source_id in source_ids:
                self._stops.stop(kind.job_type, source_id)
            return sum(
                self._job_repo.cancel(JobSelection(job_type=kind.job_type, source_id=source_id))
                for source_id in source_ids
            )
