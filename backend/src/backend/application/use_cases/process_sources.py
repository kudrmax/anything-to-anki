from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import StartedSourcesDTO
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceNotFoundError,
    TopicTargetsMissingError,
)
from backend.domain.services.source_stage import is_pending

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.use_cases.process_source import ProcessSourceUseCase
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)


class ProcessSourcesUseCase:
    """Starts processing of several sources: the chosen ones, or every pending one of a scope.
    A source that can't start any more (already started elsewhere) is skipped."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        generation_probe: TopicGenerationProbe,
        process_source: ProcessSourceUseCase,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._generation_probe = generation_probe
        self._process_source = process_source

    def pending_in(self, scope: SourceScope) -> list[int]:
        return [
            s.id for s in reversed(self._scope_resolver.sources(scope))
            if s.id is not None
            and is_pending(s.status, awaiting_generation=self._generation_probe.of(s).awaiting)
        ]

    def start(self, source_ids: Sequence[int]) -> StartedSourcesDTO:
        started: list[int] = []
        for source_id in source_ids:
            try:
                self._process_source.start(source_id)
            except (
                SourceNotFoundError,
                SourceAlreadyProcessedError,
                TopicTargetsMissingError,
            ) as e:
                logger.info("Skipped processing of source %d: %s", source_id, e)
                continue
            started.append(source_id)
        return StartedSourcesDTO(started=started)
