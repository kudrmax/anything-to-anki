from __future__ import annotations

import logging
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
from backend.domain.services.source_operations import REBUILD_OPERATION, available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import ScopeKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
    from backend.application.use_cases.refresh_topic import RefreshTopicUseCase
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.rebuild_mode import RebuildMode
    from backend.domain.value_objects.source_scope import SourceScope

logger = logging.getLogger(__name__)

Result = TypeVar("Result")

class ScopeOperationUseCase:
    """Update, Re-cut, their preview and Refresh over a set of sources; a source is a set of
    one.

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

    def check(self, scope: SourceScope, offered: SourceOperationKind) -> None:
        """Whether an operation the sources must offer as `offered` — itself or its
        preview — may start on the set: some source offers it and not every such source is
        busy."""
        targets = self._targets(scope, offered)
        if not targets:
            raise _not_supported(scope, offered)
        held = [self._lock.held(source_id) for source_id in targets]
        if all(h is not None for h in held):
            raise SourceOperationBusyError(targets[0], held[0])

    def preview(self, scope: SourceScope, mode: RebuildMode) -> RebuildPreviewDTO:
        previews, outcome = self._each(
            scope, REBUILD_OPERATION[mode],
            lambda source_id: self._rebuild_source.start(
                source_id, mode, SourceOperationKind.PREVIEW,
            ),
            lambda source_id: self._rebuild_source.run_preview(source_id, mode),
        )
        return RebuildPreviewDTO.total(mode, previews, outcome)

    def rebuild(self, scope: SourceScope, mode: RebuildMode) -> RebuildSummaryDTO:
        operation = REBUILD_OPERATION[mode]
        summaries, outcome = self._each(
            scope, operation,
            lambda source_id: self._rebuild_source.start(source_id, mode, operation),
            lambda source_id: self._rebuild_source.run(source_id, mode),
        )
        return RebuildSummaryDTO.total(mode, summaries, outcome)

    def refresh(self, scope: SourceScope) -> TopicRefreshSummaryDTO:
        refreshes, outcome = self._each(
            scope, SourceOperationKind.REFRESH, self._refresh_topic.start,
            self._refresh_topic.run,
        )
        return TopicRefreshSummaryDTO.total(refreshes, outcome)

    def _targets(self, scope: SourceScope, offered: SourceOperationKind) -> list[int]:
        return [
            source.id for source in self._scope_resolver.sources(scope)
            if source.id is not None and offered in available_operations(source)
        ]

    def _each(
        self,
        scope: SourceScope,
        offered: SourceOperationKind,
        start: Callable[[int], None],
        run: Callable[[int], Result],
    ) -> tuple[list[Result], SetOutcomeDTO]:
        targets = self._targets(scope, offered)
        results: list[Result] = []
        skipped = 0
        errors: list[Exception] = []
        for source_id in targets:
            try:
                start(source_id)
            except SourceOperationBusyError:
                self._unit_of_work.rollback()
                logger.info("%s: source %d is busy, skipped", offered.value, source_id)
                skipped += 1
                continue
            except DomainError as e:
                self._unit_of_work.rollback()
                logger.exception("%s: source %d can't start", offered.value, source_id)
                errors.append(e)
                continue
            self._unit_of_work.commit()
            try:
                results.append(run(source_id))
            except Exception as e:
                logger.exception("%s: source %d failed", offered.value, source_id)
                errors.append(e)
        if errors and len(errors) == len(targets):
            raise errors[0]
        return results, SetOutcomeDTO(skipped=skipped, failed=len(errors))


def _not_supported(scope: SourceScope, kind: SourceOperationKind) -> DomainError:
    source_id = scope.source_id if scope.kind is ScopeKind.SOURCE else None
    if kind is SourceOperationKind.REFRESH:
        return RefreshNotSupportedError(source_id, scope=scope.token)
    return RebuildNotSupportedError(source_id, scope=scope.token)
