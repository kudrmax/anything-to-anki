from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar

from backend.application.dto.rebuild_dtos import (
    RebuildPreviewDTO,
    RebuildSummaryDTO,
    SetOutcomeDTO,
    TopicRefreshSummaryDTO,
)
from backend.domain.exceptions import (
    DomainError,
    RebuildNotSupportedError,
    RefreshNotSupportedError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import ScopeKind

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
    from backend.application.use_cases.refresh_topic import RefreshTopicUseCase
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)

Result = TypeVar("Result")

# The operation a source must offer for each kind that runs over a set.
_OFFERED: Mapping[SourceOperationKind, SourceOperationKind] = MappingProxyType({
    SourceOperationKind.REBUILD: SourceOperationKind.REBUILD,
    SourceOperationKind.PREVIEW: SourceOperationKind.REBUILD,
    SourceOperationKind.REFRESH: SourceOperationKind.REFRESH,
})


class ScopeOperationUseCase:
    """Rebuild, its preview and Refresh over a set of sources; a source is a set of one.

    The sources offering the operation take their turns in the set's order: each is taken
    only when its turn comes, one busy then is skipped, one that fails is counted and the
    rest go on. The results are summed; the operation fails only if every source failed.
    """

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        rebuild_source: RebuildSourceUseCase,
        refresh_topic: RefreshTopicUseCase,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._rebuild_source = rebuild_source
        self._refresh_topic = refresh_topic
        self._lock = lock
        self._unit_of_work = unit_of_work

    def check(self, scope: SourceScope, kind: SourceOperationKind) -> None:
        """Whether the operation may start on the set: some source offers it and not every
        such source is busy."""
        targets = self._targets(scope, kind)
        if not targets:
            raise _not_supported(scope, kind)
        held = [self._lock.held(source_id) for source_id in targets]
        if all(h is not None for h in held):
            raise SourceOperationBusyError(targets[0], held[0])

    def preview(self, scope: SourceScope) -> RebuildPreviewDTO:
        previews, outcome = self._each(
            scope, SourceOperationKind.PREVIEW, self._rebuild_source.run_preview,
        )
        return RebuildPreviewDTO.total(previews, outcome)

    def rebuild(self, scope: SourceScope, include_open: bool) -> RebuildSummaryDTO:
        summaries, outcome = self._each(
            scope, SourceOperationKind.REBUILD,
            lambda source_id: self._rebuild_source.run(source_id, include_open),
        )
        return RebuildSummaryDTO.total(summaries, outcome)

    def refresh(self, scope: SourceScope) -> TopicRefreshSummaryDTO:
        refreshes, outcome = self._each(
            scope, SourceOperationKind.REFRESH, self._refresh_topic.run,
        )
        return TopicRefreshSummaryDTO.total(refreshes, outcome)

    def _targets(self, scope: SourceScope, kind: SourceOperationKind) -> list[int]:
        offered = _OFFERED[kind]
        return [
            source.id for source in self._scope_resolver.sources(scope)
            if source.id is not None and offered in available_operations(source)
        ]

    def _each(
        self,
        scope: SourceScope,
        kind: SourceOperationKind,
        run: Callable[[int], Result],
    ) -> tuple[list[Result], SetOutcomeDTO]:
        targets = self._targets(scope, kind)
        results: list[Result] = []
        skipped = 0
        errors: list[Exception] = []
        for source_id in targets:
            try:
                self._start(source_id, kind)
            except SourceOperationBusyError:
                self._unit_of_work.rollback()
                logger.info("%s: source %d is busy, skipped", kind.value, source_id)
                skipped += 1
                continue
            except DomainError as e:
                self._unit_of_work.rollback()
                logger.exception("%s: source %d can't start", kind.value, source_id)
                errors.append(e)
                continue
            self._unit_of_work.commit()
            try:
                results.append(run(source_id))
            except Exception as e:
                logger.exception("%s: source %d failed", kind.value, source_id)
                errors.append(e)
        if errors and len(errors) == len(targets):
            raise errors[0]
        return results, SetOutcomeDTO(skipped=skipped, failed=len(errors))

    def _start(self, source_id: int, kind: SourceOperationKind) -> None:
        if kind is SourceOperationKind.REFRESH:
            self._refresh_topic.start(source_id)
        else:
            self._rebuild_source.start(source_id, kind)


def _not_supported(scope: SourceScope, kind: SourceOperationKind) -> DomainError:
    source_id = scope.source_id if scope.kind is ScopeKind.SOURCE else None
    if kind is SourceOperationKind.REFRESH:
        return RefreshNotSupportedError(source_id, scope=scope.token)
    return RebuildNotSupportedError(source_id, scope=scope.token)
