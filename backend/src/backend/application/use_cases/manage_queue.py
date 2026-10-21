from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.generation_stops import GenerationStops
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.job_selection import JobSelection

logger = logging.getLogger(__name__)


class ManageQueueUseCase:
    """The user's actions on queued, running and failed jobs.

    A cancelled running job stops being RUNNING at once; the worker drops its
    result when the work finishes. Cancelling a kind or a source, not one job, also stops a
    run of generation still queueing it.
    """

    def __init__(
        self, job_repo: JobRepository, unit_of_work: UnitOfWork, stops: GenerationStops,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._job_repo = job_repo
        self._stops = stops

    def cancel(self, selection: JobSelection) -> int:
        with self._unit_of_work.write():
            if selection.job_id is None and selection.error is None:
                self._stops.stop(selection.job_type, selection.source_id)
            count = self._job_repo.cancel(selection)
        logger.info("queue: cancelled %d jobs (%s)", count, selection)
        return count

    def retry(self, selection: JobSelection) -> int:
        with self._unit_of_work.write():
            count = self._job_repo.retry(selection)
        logger.info("queue: retried %d jobs (%s)", count, selection)
        return count

    def dismiss(self, selection: JobSelection) -> int:
        with self._unit_of_work.write():
            count = self._job_repo.dismiss(selection)
        logger.info("queue: dismissed %d jobs (%s)", count, selection)
        return count
