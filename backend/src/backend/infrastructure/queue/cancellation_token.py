from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUser

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository


class CancellationToken:
    """Cooperative cancellation check for running jobs.

    The cancel endpoint deletes the job row from the DB.
    The worker passes this token to handlers, which call check()
    between atomic steps. If the job row is gone, CancelledByUser is raised.
    """

    def __init__(self, job_id: int, job_repo: JobRepository) -> None:
        self._job_id = job_id
        self._job_repo = job_repo

    def check(self) -> None:
        """Raise CancelledByUser if the job has been deleted (cancelled)."""
        if not self._job_repo.job_exists(self._job_id):
            raise CancelledByUser(self._job_id)

    @property
    def is_cancelled(self) -> bool:
        """Non-raising check for cancellation."""
        return not self._job_repo.job_exists(self._job_id)
