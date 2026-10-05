from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.job_selection import JobSelection

logger = logging.getLogger(__name__)


class ManageQueueUseCase:
    """The user's actions on queued, running and failed jobs.

    A cancelled running job stops being RUNNING at once; the worker drops its
    result when the work finishes.
    """

    def __init__(self, job_repo: JobRepository) -> None:
        self._job_repo = job_repo

    def cancel(self, selection: JobSelection) -> int:
        count = self._job_repo.cancel(selection)
        logger.info("queue: cancelled %d jobs (%s)", count, selection)
        return count

    def retry(self, selection: JobSelection) -> int:
        count = self._job_repo.retry(selection)
        logger.info("queue: retried %d jobs (%s)", count, selection)
        return count

    def dismiss(self, selection: JobSelection) -> int:
        count = self._job_repo.dismiss(selection)
        logger.info("queue: dismissed %d jobs (%s)", count, selection)
        return count
