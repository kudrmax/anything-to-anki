from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from backend.domain.exceptions import CancelledByUserError
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.job_type import JobType
    from backend.infrastructure.persistence.session_work import SessionBuild, SessionWork


class SqlaJobQueue:
    """The worker's side of the jobs table. Claiming and finishing runs is a write of its
    own each time; the work of a claimed run writes only while the run is still claimed."""

    def __init__(self, work: SessionWork) -> None:
        self._work = work

    def requeue_running(self) -> int:
        return self._work.write(lambda session: _jobs(session).requeue_running())

    def claim_next_run(
        self,
        run_limits: Mapping[JobType, int],
        accepted_types: frozenset[JobType] | None = None,
        mixed_source_types: frozenset[JobType] = frozenset(),
    ) -> list[Job]:
        return self._work.write(lambda session: _jobs(session).claim_next_run(
            run_limits, accepted_types=accepted_types, mixed_source_types=mixed_source_types,
        ))

    def complete(self, jobs: list[Job]) -> None:
        self._work.write(lambda session: _jobs(session).complete(jobs))

    def fail(self, job_ids: list[int], error: str) -> None:
        self._work.write(lambda session: _jobs(session).fail(job_ids, error))

    def fail_running(self, job_type: JobType, error: str) -> int:
        return self._work.write(
            lambda session: _jobs(session).fail_running(job_type, error),
        )

    def get(self, job_id: int) -> Job | None:
        return self._work.read(lambda session: _jobs(session).get(job_id))

    def still_claimed(self, jobs: list[Job]) -> set[int]:
        """The jobs still RUNNING under the claim that took them."""
        return self._work.read(lambda session: _jobs(session).still_claimed(jobs))

    @contextmanager
    def claimed[T](self, jobs: list[Job], build: SessionBuild[T]) -> Iterator[T]:
        """What `build` makes of a session of its own, for the work of the claimed `jobs`.

        The user may cancel the jobs, or the worker fail them by timeout, while the work
        is still going. Each write of the work commits only if some of them are still
        claimed; otherwise it rolls back with CancelledByUserError. A block that ends
        after they are all gone raises it too, saying whether a write of it committed
        before that."""
        passed_checks = 0

        def require_claimed(session: Session) -> None:
            nonlocal passed_checks
            _require_claimed(_jobs(session).still_claimed(jobs), jobs)
            passed_checks += 1

        with self._work.open(build, commit_check=require_claimed) as built:
            yield built
        _require_claimed(self.still_claimed(jobs), jobs, wrote=passed_checks > 0)


def _require_claimed(claimed: set[int], jobs: list[Job], wrote: bool = False) -> None:
    if not claimed:
        raise CancelledByUserError([j.id for j in jobs if j.id is not None], wrote=wrote)


def _jobs(session: Session) -> SqlaJobRepository:
    """The jobs on the session, recording on the session's own recorder."""
    return SqlaJobRepository(session, SessionChangeRecorder(session))
