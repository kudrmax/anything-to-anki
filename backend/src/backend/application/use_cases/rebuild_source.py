from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import (
    RebuildCountsDTO,
    RebuildPreviewDTO,
    RebuildSummaryDTO,
)
from backend.application.utils.long_operation_runner import Applied, SourceWork
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import REBUILD_OPERATION, available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.application.utils.long_operation_runner import (
        LongOperationRunner,
        OperationResult,
    )
    from backend.application.utils.source_rebuilder import AnalysedSource, SourceRebuilder
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.services.long_operation_progress import PartReport
    from backend.domain.value_objects.rebuild_mode import RebuildMode

logger = logging.getLogger(__name__)


class RebuildSourceUseCase:
    """Updates or re-cuts sources by the current logic, level and knowledge without losing
    the user's work.

    The Update or Re-cut of sources is one long operation: `rebuild` runs it once its lock
    is held. Its preview writes nothing and holds only its source: `start` takes the source
    inside a write its caller opens, committed before `run_preview`, which frees it whatever
    happens; `preview` does all of it.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        rebuilder: SourceRebuilder,
        runner: LongOperationRunner,
    ) -> None:
        self._source_repo = source_repo
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._rebuilder = rebuilder
        self._runner = runner

    def check(self, source_id: int, mode: RebuildMode) -> None:
        """Raises why the source cannot be rebuilt in `mode`."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if REBUILD_OPERATION[mode] not in available_operations(source):
            raise RebuildNotSupportedError(source_id)

    def start(self, source_id: int, mode: RebuildMode, kind: SourceOperationKind) -> None:
        """Takes the source for the preview of the rebuild in `mode`."""
        self.check(source_id, mode)
        if not self._lock.acquire(source_id, kind):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def rebuild(
        self, targets: Callable[[], list[int]], mode: RebuildMode,
    ) -> OperationResult[RebuildSummaryDTO] | None:
        """The sources `targets` reads, rebuilt in `mode` together; None when cancelled."""
        return self._runner.run(_Rebuild(targets, mode, self._rebuilder))

    def execute(self, source_id: int, mode: RebuildMode) -> RebuildSummaryDTO | None:
        """One source rebuilt as a long operation of its own; its failure is raised."""
        with self._unit_of_work.read():
            self.check(source_id, mode)
        result = self.rebuild(lambda: [source_id], mode)
        if result is None:
            return None
        if result.failures:
            raise result.failures[0][1]
        [summary] = result.results
        return summary

    def preview(self, source_id: int, mode: RebuildMode) -> RebuildPreviewDTO:
        with self._unit_of_work.write():
            self.start(source_id, mode, SourceOperationKind.PREVIEW)
        return self.run_preview(source_id, mode)

    def run_preview(self, source_id: int, mode: RebuildMode) -> RebuildPreviewDTO:
        """The analysis and the plan; nothing is written."""
        try:
            plan = self._rebuilder.plan(self._rebuilder.analyse(source_id), mode)
            return RebuildPreviewDTO(mode=mode, counts=RebuildCountsDTO.of(plan))
        finally:
            self._release(source_id)

    def _release(self, source_id: int) -> None:
        with self._unit_of_work.write():
            self._lock.release(source_id)
        logger.info("rebuild: source freed (source_id=%d)", source_id)


class _Rebuild(SourceWork["AnalysedSource", RebuildSummaryDTO]):
    """A source that fails is counted; the others are rebuilt."""

    def __init__(
        self, targets: Callable[[], list[int]], mode: RebuildMode, rebuilder: SourceRebuilder,
    ) -> None:
        self._read_targets = targets
        self._mode = mode
        self._rebuilder = rebuilder

    def targets(self) -> list[int]:
        return self._read_targets()

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        return self._rebuilder.sizes(source_ids)

    def prepare(self, source_id: int, report: PartReport) -> AnalysedSource:
        return self._rebuilder.analyse(source_id, report=report)

    def apply(self, prepared: AnalysedSource) -> Applied[RebuildSummaryDTO]:
        applied = self._rebuilder.apply_inside(prepared, self._mode)
        summary = RebuildSummaryDTO(mode=self._mode, counts=RebuildCountsDTO.of(applied.plan))
        return Applied(summary, applied.dropped_files)

    def failed(self, source_id: int, error: Exception) -> None:
        logger.info("rebuild: source %d failed: %s", source_id, error)
