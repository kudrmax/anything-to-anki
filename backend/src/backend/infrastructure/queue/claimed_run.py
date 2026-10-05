from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job
    from backend.infrastructure.container import Container


class ClaimedRun:
    """Jobs claimed together from the head of the queue, and the guard on their results.

    The user may cancel a job, or the worker may fail it by timeout, while its
    work is still going. Work writes through ``session()``, which commits only
    if some of the jobs are still RUNNING under this claim when the work ends; otherwise it
    rolls back and raises CancelledByUserError. A batch that lost only some of
    its jobs filters its writes with ``still_wanted``.
    """

    def __init__(self, container: Container, jobs: list[Job]) -> None:
        assert jobs, "a run has at least one job"
        self._container = container
        self.jobs = jobs

    @property
    def head(self) -> Job:
        return self.jobs[0]

    @property
    def candidate_ids(self) -> list[int]:
        return [j.candidate_id for j in self.jobs if j.candidate_id is not None]

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._container.session_scope() as session:
            yield session
            if not self._still_claimed():
                raise CancelledByUserError(self._job_ids())

    def still_wanted(self, candidate_ids: list[int]) -> set[int]:
        claimed = self._still_claimed()
        return {
            j.candidate_id for j in self.jobs
            if j.candidate_id is not None and j.candidate_id in candidate_ids
            and j.id in claimed
        }

    def _still_claimed(self) -> set[int]:
        with self._container.session_scope() as session:
            return SqlaJobRepository(session).still_claimed(self.jobs)

    def _job_ids(self) -> list[int]:
        return [j.id for j in self.jobs if j.id is not None]
