from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import StartedSourcesDTO
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceNotFoundError,
    SourceOperationBusyError,
    TopicTargetsMissingError,
)
from backend.domain.services.source_stage import is_pending

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.use_cases.process_source import ProcessSourceUseCase
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)


class ProcessSourcesUseCase:
    """Which of several sources — the chosen ones, or every pending one of a scope — may be
    processed: a source that can't (missing, already processed, busy, no topic targets) is
    skipped. The rest are processed together by ProcessSourceUseCase.run, as one long
    operation."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        generation_probe: TopicGenerationProbe,
        process_source: ProcessSourceUseCase,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._lock = lock
        self._scope_resolver = scope_resolver
        self._generation_probe = generation_probe
        self._process_source = process_source

    def pending_in(self, scope: SourceScope) -> list[int]:
        busy = self._lock.operations()
        return [
            s.id for s in self._scope_resolver.oldest_added_first(scope)
            if s.id is not None
            and is_pending(
                s.status,
                awaiting_generation=self._generation_probe.of(s).awaiting,
                busy=s.id in busy,
            )
        ]

    def check(self, source_ids: Sequence[int]) -> StartedSourcesDTO:
        with self._unit_of_work.read():
            return self._checked(source_ids)

    def _checked(self, source_ids: Sequence[int]) -> StartedSourcesDTO:
        started: list[int] = []
        skipped: list[int] = []
        for source_id in source_ids:
            try:
                self._process_source.check(source_id)
            except (
                SourceNotFoundError,
                SourceAlreadyProcessedError,
                SourceOperationBusyError,
                TopicTargetsMissingError,
            ) as e:
                logger.info("Skipped processing of source %d: %s", source_id, e)
                skipped.append(source_id)
                continue
            started.append(source_id)
        return StartedSourcesDTO(started=started, skipped=skipped)
