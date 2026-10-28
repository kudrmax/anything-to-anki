from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.value_objects.export_group import ExportGroup

if TYPE_CHECKING:
    from backend.application.utils.card_fill import CardFillPlanner
    from backend.application.utils.export_queue import ExportQueue
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)


class FillIncompleteCardsUseCase:
    """Queues the generation of every part the incomplete export cards of a set lack.
    A part nothing can make now (no video, no phrase time, a busy source, cloze words to
    pick) is skipped, as the export shows it."""

    def __init__(
        self,
        export_queue: ExportQueue,
        scope_resolver: SourceScopeResolver,
        planner: CardFillPlanner,
        job_repo: JobRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._export_queue = export_queue
        self._scope_resolver = scope_resolver
        self._planner = planner
        self._job_repo = job_repo
        self._unit_of_work = unit_of_work

    def execute(self, scope: SourceScope) -> int:
        """Returns how many jobs were queued."""
        with self._unit_of_work.write():
            batch = self._export_queue.for_sources(
                [s.id for s in self._scope_resolver.sources(scope) if s.id is not None],
            )
            plan = self._planner.plan(batch.in_group(ExportGroup.INCOMPLETE))
            queued = len(self._job_repo.enqueue(plan.jobs))
        logger.info("fill_incomplete_cards: queued (scope=%s, jobs=%d)", scope.token, queued)
        return queued
