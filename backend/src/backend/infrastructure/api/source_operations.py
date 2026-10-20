from __future__ import annotations

import itertools
import threading
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import OperationState, SourceOperationDTO

if TYPE_CHECKING:
    from backend.application.dto.rebuild_dtos import (
        RebuildPreviewDTO,
        RebuildSummaryDTO,
        TopicRefreshSummaryDTO,
    )
    from backend.domain.value_objects.source_operation_kind import SourceOperationKind


class SourceOperationRegistry:
    """The last long operation started on each source, and its result once it is done.

    Kept in memory: after a restart no operation runs, and the results are gone with them.
    """

    def __init__(self) -> None:
        self._last: dict[int, SourceOperationDTO] = {}
        self._ids = itertools.count(1)
        self._guard = threading.Lock()

    def started(self, source_id: int, kind: SourceOperationKind) -> SourceOperationDTO:
        with self._guard:
            operation = SourceOperationDTO.running(next(self._ids), kind)
            self._last[source_id] = operation
            return operation

    def finished(
        self,
        source_id: int,
        operation_id: int,
        *,
        preview: RebuildPreviewDTO | None = None,
        summary: RebuildSummaryDTO | None = None,
        refresh: TopicRefreshSummaryDTO | None = None,
    ) -> None:
        self._update(source_id, operation_id, {
            "state": OperationState.DONE, "preview": preview, "summary": summary,
            "refresh": refresh,
        })

    def failed(self, source_id: int, operation_id: int, error: str) -> None:
        self._update(source_id, operation_id, {"state": OperationState.ERROR, "error": error})

    def last(self, source_id: int) -> SourceOperationDTO | None:
        with self._guard:
            return self._last.get(source_id)

    def _update(self, source_id: int, operation_id: int, changes: dict[str, object]) -> None:
        with self._guard:
            current = self._last.get(source_id)
            if current is not None and current.operation_id == operation_id:
                self._last[source_id] = current.model_copy(update=changes)


OPERATIONS = SourceOperationRegistry()
