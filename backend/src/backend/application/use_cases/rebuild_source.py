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
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.utils.source_rebuilder import SourceRebuilder
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class RebuildSourceUseCase:
    """Rebuilds a source by the current logic, level and knowledge without losing work.

    `start` takes the source for the operation and must be committed before `run` or
    `run_preview`, which free it whatever happens; `execute` and `preview` do all of it.
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

    def start(self, source_id: int, kind: SourceOperationKind) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if SourceOperationKind.REBUILD not in available_operations(source):
            raise RebuildNotSupportedError(source_id)
        if not self._lock.acquire(source_id, kind):
            raise SourceOperationBusyError(source_id, self._lock.held(source_id))

    def execute(self, source_id: int, include_open: bool) -> RebuildSummaryDTO:
        self.start(source_id, SourceOperationKind.REBUILD)
        self._unit_of_work.commit()
        return self.run(source_id, include_open)

    def preview(self, source_id: int) -> RebuildPreviewDTO:
        self.start(source_id, SourceOperationKind.PREVIEW)
        self._unit_of_work.commit()
        return self.run_preview(source_id)

    def run(self, source_id: int, include_open: bool) -> RebuildSummaryDTO:
        try:
            analysed = self._rebuilder.analyse(source_id)
            has_text = analysed.words is not None
            plan = self._rebuilder.apply(analysed, include_open)
            return RebuildSummaryDTO(
                include_open=include_open and has_text, counts=RebuildCountsDTO.of(plan),
            )
        finally:
            self._release(source_id)

    def run_preview(self, source_id: int) -> RebuildPreviewDTO:
        """The analysis and both plans; nothing is written."""
        try:
            analysed = self._rebuilder.analyse(source_id)
            without_open = RebuildCountsDTO.of(self._rebuilder.plan(analysed, False))
            if analysed.words is None:
                return RebuildPreviewDTO(without_open=without_open, with_open=None)
            return RebuildPreviewDTO(
                without_open=without_open,
                with_open=RebuildCountsDTO.of(self._rebuilder.plan(analysed, True)),
            )
        finally:
            self._release(source_id)

    def _release(self, source_id: int) -> None:
        self._unit_of_work.rollback()
        self._lock.release(source_id)
        self._unit_of_work.commit()
        logger.info("rebuild: source freed (source_id=%d)", source_id)
