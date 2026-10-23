from __future__ import annotations

import itertools
import threading
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import OperationState, SourceOperationDTO
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.dto.rebuild_dtos import (
        RebuildPreviewDTO,
        RebuildSummaryDTO,
        TopicRefreshSummaryDTO,
    )


class SourceOperationRegistry:
    """The last long operation started on each set of sources, by the set's token, and its
    result once it is done.

    Kept in memory: after a restart no operation runs, and the results are gone with them.
    """

    def __init__(self) -> None:
        self._last: dict[str, SourceOperationDTO] = {}
        self._ids = itertools.count(1)
        self._guard = threading.Lock()

    def started(self, scope: str, kind: SourceOperationKind) -> SourceOperationDTO:
        with self._guard:
            operation = SourceOperationDTO.running(next(self._ids), kind)
            self._last[scope] = operation
            return operation

    def finished(
        self,
        scope: str,
        operation_id: int,
        *,
        preview: RebuildPreviewDTO | None = None,
        summary: RebuildSummaryDTO | None = None,
        refresh: TopicRefreshSummaryDTO | None = None,
    ) -> None:
        self._update(scope, operation_id, {
            "state": OperationState.DONE, "preview": preview, "summary": summary,
            "refresh": refresh,
        })

    def failed(self, scope: str, operation_id: int, error: str) -> None:
        self._update(scope, operation_id, {"state": OperationState.ERROR, "error": error})

    def preview_running(self) -> bool:
        """A preview runs: it reads what a long operation would rewrite."""
        with self._guard:
            return any(
                op.state is OperationState.RUNNING and op.kind is SourceOperationKind.PREVIEW
                for op in self._last.values()
            )

    def forget(self, scope: str, operation_id: int) -> None:
        """An operation that did not start after all."""
        with self._guard:
            current = self._last.get(scope)
            if current is not None and current.operation_id == operation_id:
                del self._last[scope]

    def last(self, scope: str) -> SourceOperationDTO | None:
        with self._guard:
            return self._last.get(scope)

    def _update(self, scope: str, operation_id: int, changes: dict[str, object]) -> None:
        with self._guard:
            current = self._last.get(scope)
            if current is not None and current.operation_id == operation_id:
                self._last[scope] = current.model_copy(update=changes)


OPERATIONS = SourceOperationRegistry()
