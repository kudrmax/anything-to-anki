from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.phrase_ref import PhraseRef

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from backend.domain.entities.job import Job
    from backend.infrastructure.persistence.session_work import SessionBuild
    from backend.infrastructure.persistence.sqla_job_queue import SqlaJobQueue


class ClaimedRun:
    """Jobs claimed together from the head of the queue, and the guard on their results.

    The user may cancel a job, or the worker may fail it by timeout, while its work is
    still going. The work's use cases come from ``use_case()``: their writes commit only
    while some of the jobs are still RUNNING under this claim, and otherwise roll back
    with CancelledByUserError. A batch that lost only some of its jobs filters its writes
    with ``still_wanted``.
    """

    def __init__(self, queue: SqlaJobQueue, jobs: list[Job]) -> None:
        assert jobs, "a run has at least one job"
        self._queue = queue
        self.jobs = jobs

    @property
    def head(self) -> Job:
        return self.jobs[0]

    @property
    def phrases(self) -> list[PhraseRef]:
        """The phrases of the run's phrase jobs, at the revisions the jobs expect."""
        return [ref for ref in map(phrase_of, self.jobs) if ref is not None]

    def use_case[T](self, build: SessionBuild[T]) -> AbstractContextManager[T]:
        return self._queue.claimed(self.jobs, build)

    def still_wanted(self, phrase_ids: list[int]) -> set[int]:
        claimed = self._queue.still_claimed(self.jobs)
        return {
            j.phrase_id for j in self.jobs
            if j.phrase_id is not None and j.phrase_id in phrase_ids and j.id in claimed
        }


def phrase_of(job: Job) -> PhraseRef | None:
    """The phrase a phrase job works on; None for a job of a word or a source."""
    if job.phrase_id is None or job.phrase_revision is None:
        return None
    return PhraseRef(job.phrase_id, job.phrase_revision)
