from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.rebuild_dtos import (
    RebuildCountsDTO,
    RebuildPreviewDTO,
    RebuildSummaryDTO,
)
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import REBUILD_OPERATION, available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.utils.source_rebuilder import SourceRebuilder
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.rebuild_mode import RebuildMode

logger = logging.getLogger(__name__)


class RebuildSourceUseCase:
    """Updates or re-cuts a source by the current logic, level and knowledge without losing
    the user's work.

    `start` takes the source for the operation inside a write its caller opens, committed
    before `run` or `run_preview`, which free it whatever happens; `execute` and `preview`
    do all of it.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
        rebuilder: SourceRebuilder,
    ) -> None:
        self._source_repo = source_repo
        self._lock = lock
        self._unit_of_work = unit_of_work
        self._rebuilder = rebuilder

    def start(self, source_id: int, mode: RebuildMode, kind: SourceOperationKind) -> None:
        """Takes the source for `kind`: the rebuild in `mode` or its preview."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if REBUILD_OPERATION[mode] not in available_operations(source):
            raise RebuildNotSupportedError(source_id)
        if not self._lock.acquire(source_id, kind):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def execute(self, source_id: int, mode: RebuildMode) -> RebuildSummaryDTO:
        with self._unit_of_work.write():
            self.start(source_id, mode, REBUILD_OPERATION[mode])
        return self.run(source_id, mode)

    def preview(self, source_id: int, mode: RebuildMode) -> RebuildPreviewDTO:
        with self._unit_of_work.write():
            self.start(source_id, mode, SourceOperationKind.PREVIEW)
        return self.run_preview(source_id, mode)

    def run(self, source_id: int, mode: RebuildMode) -> RebuildSummaryDTO:
        try:
            plan = self._rebuilder.apply(self._rebuilder.analyse(source_id), mode)
            return RebuildSummaryDTO(mode=mode, counts=RebuildCountsDTO.of(plan))
        finally:
            self._release(source_id)

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
