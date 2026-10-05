from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from itertools import takewhile
from typing import TYPE_CHECKING

from sqlalchemy import CursorResult, and_, delete, func, or_, select, update

from backend.domain.ports.job_repository import DEFAULT_RUN_LIMIT, JobRepository
from backend.domain.value_objects.failed_job_group import FailedJobGroup
from backend.domain.value_objects.job_selection import UNKNOWN_JOB_ERROR
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.models import JobModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy import ColumnElement, Delete, Update
    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.job_selection import JobSelection

_ACTIVE_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value)
_QUEUE_ORDER = (JobModel.created_at.asc(), JobModel.id.asc())


def _same_key(job_type: str, source_id: int, candidate_id: int | None) -> ColumnElement[bool]:
    if candidate_id is not None:
        return and_(JobModel.job_type == job_type, JobModel.candidate_id == candidate_id)
    return and_(
        JobModel.job_type == job_type,
        JobModel.source_id == source_id,
        JobModel.candidate_id.is_(None),
    )


def _selected(selection: JobSelection) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if selection.job_type is not None:
        clauses.append(JobModel.job_type == selection.job_type.value)
    if selection.source_id is not None:
        clauses.append(JobModel.source_id == selection.source_id)
    if selection.job_id is not None:
        clauses.append(JobModel.id == selection.job_id)
    if selection.error is not None:
        if selection.error == UNKNOWN_JOB_ERROR:
            clauses.append(or_(JobModel.error.is_(None), JobModel.error == UNKNOWN_JOB_ERROR))
        else:
            clauses.append(JobModel.error == selection.error)
    return clauses


class SqlaJobRepository(JobRepository):
    """SQLAlchemy implementation of JobRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Lifecycle ────────────────────────────────────────────────────

    def enqueue(self, jobs: list[Job]) -> list[Job]:
        models: list[JobModel] = []
        seen: set[tuple[str, int, int | None]] = set()
        for job in jobs:
            key = (job.job_type.value, job.source_id, job.candidate_id)
            if key in seen or self._is_active(*key):
                continue
            seen.add(key)
            self._session.execute(
                delete(JobModel).where(
                    _same_key(*key), JobModel.status == JobStatus.FAILED.value,
                )
            )
            model = JobModel.from_entity(job)
            model.status = JobStatus.QUEUED.value
            model.error = None
            model.started_at = None
            models.append(model)
        self._session.add_all(models)
        self._session.flush()
        return [m.to_entity() for m in models]

    def claim_next_run(
        self,
        run_limits: Mapping[JobType, int],
        accepted_types: frozenset[JobType] | None = None,
    ) -> list[Job]:
        fetch_size = max([DEFAULT_RUN_LIMIT, *run_limits.values()])
        stmt = (
            select(JobModel)
            .where(JobModel.status == JobStatus.QUEUED.value)
            .order_by(*_QUEUE_ORDER)
            .limit(fetch_size)
        )
        queued = list(self._session.execute(stmt).scalars().all())
        if not queued:
            return []
        head = queued[0]
        head_type = JobType(head.job_type)
        if accepted_types is not None and head_type not in accepted_types:
            return []

        run_limit = run_limits.get(head_type, DEFAULT_RUN_LIMIT)
        run = list(takewhile(
            lambda m: m.job_type == head.job_type and m.source_id == head.source_id,
            queued[:run_limit],
        ))
        now = datetime.now(tz=UTC)
        for model in run:
            model.status = JobStatus.RUNNING.value
            model.started_at = now
        self._session.flush()
        return [m.to_entity() for m in run]

    def running_ids(self, job_ids: list[int]) -> set[int]:
        if not job_ids:
            return set()
        stmt = select(JobModel.id).where(
            JobModel.id.in_(job_ids), JobModel.status == JobStatus.RUNNING.value,
        )
        return set(self._session.execute(stmt).scalars().all())

    def complete(self, jobs: list[Job]) -> None:
        job_ids = [j.id for j in jobs if j.id is not None]
        if job_ids:
            self._session.execute(delete(JobModel).where(JobModel.id.in_(job_ids)))
        for job in jobs:
            self._session.execute(
                delete(JobModel).where(
                    _same_key(job.job_type.value, job.source_id, job.candidate_id),
                    JobModel.status == JobStatus.FAILED.value,
                )
            )
        self._session.flush()

    def fail(self, job_ids: list[int], error: str) -> None:
        if not job_ids:
            return
        self._session.execute(
            update(JobModel)
            .where(JobModel.id.in_(job_ids), JobModel.status == JobStatus.RUNNING.value)
            .values(status=JobStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def requeue_running(self) -> int:
        return self._affected(
            update(JobModel)
            .where(JobModel.status == JobStatus.RUNNING.value)
            .values(status=JobStatus.QUEUED.value, started_at=None)
        )

    def fail_running(self, job_type: JobType, error: str) -> int:
        return self._affected(
            update(JobModel)
            .where(
                JobModel.status == JobStatus.RUNNING.value,
                JobModel.job_type == job_type.value,
            )
            .values(status=JobStatus.FAILED.value, error=error)
        )

    # ── User actions ─────────────────────────────────────────────────

    def cancel(self, selection: JobSelection) -> int:
        return self._affected(
            delete(JobModel).where(JobModel.status.in_(_ACTIVE_STATUSES), *_selected(selection))
        )

    def dismiss(self, selection: JobSelection) -> int:
        return self._affected(
            delete(JobModel).where(
                JobModel.status == JobStatus.FAILED.value, *_selected(selection),
            )
        )

    def retry(self, selection: JobSelection) -> int:
        stmt = (
            select(JobModel)
            .where(JobModel.status == JobStatus.FAILED.value, *_selected(selection))
            .order_by(*_QUEUE_ORDER)
        )
        failed = list(self._session.execute(stmt).scalars().all())
        now = datetime.now(tz=UTC)
        retried = 0
        for model in failed:
            if self._is_active(model.job_type, model.source_id, model.candidate_id):
                self._session.delete(model)
                continue
            model.status = JobStatus.QUEUED.value
            model.error = None
            model.started_at = None
            model.created_at = now
            retried += 1
        self._session.flush()
        return retried

    # ── Reads ────────────────────────────────────────────────────────

    def get(self, job_id: int) -> Job | None:
        model = self._session.get(JobModel, job_id)
        return model.to_entity() if model is not None else None

    def has_active_jobs_for_source(
        self, source_id: int, job_types: frozenset[JobType] | None = None,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(
                JobModel.source_id == source_id,
                JobModel.status.in_(_ACTIVE_STATUSES),
            )
        )
        if job_types is not None:
            stmt = stmt.where(
                JobModel.job_type.in_([jt.value for jt in job_types])
            )
        return self._session.execute(stmt).scalar_one() > 0

    def get_queue_summary(
        self, source_id: int | None = None,
    ) -> dict[str, dict[str, int]]:
        stmt = (
            select(
                JobModel.job_type,
                JobModel.status,
                func.count(),
            )
            .group_by(JobModel.job_type, JobModel.status)
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        rows = self._session.execute(stmt).all()
        result: dict[str, dict[str, int]] = {
            jt.value: {"queued": 0, "running": 0, "failed": 0}
            for jt in JobType
        }
        for job_type_val, status_val, cnt in rows:
            if job_type_val in result and status_val in result[job_type_val]:
                result[job_type_val][status_val] = cnt
        return result

    def get_jobs_for_candidates(
        self, candidate_ids: list[int],
    ) -> dict[int, dict[str, Job]]:
        if not candidate_ids:
            return {}
        stmt = (
            select(JobModel)
            .where(JobModel.candidate_id.in_(candidate_ids))
            .order_by(
                # Order so that queued/running come last (we keep last per candidate_id+type)
                JobModel.status.asc(),
            )
        )
        rows = self._session.execute(stmt).scalars().all()
        # Build mapping; later rows overwrite earlier ones per (candidate_id, job_type).
        # Status ordering: "failed" < "queued" < "running" (alphabetical asc)
        # So queued/running overwrite failed — which is the desired behavior.
        result: dict[int, dict[str, Job]] = {}
        for model in rows:
            if model.candidate_id is not None:
                if model.candidate_id not in result:
                    result[model.candidate_id] = {}
                result[model.candidate_id][model.job_type] = model.to_entity()
        return result

    def get_jobs_by_status(
        self,
        statuses: list[JobStatus],
        source_id: int | None = None,
        job_type: JobType | None = None,
        limit: int | None = None,
    ) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(JobModel.status.in_([s.value for s in statuses]))
            .order_by(*_QUEUE_ORDER)
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        if job_type is not None:
            stmt = stmt.where(JobModel.job_type == job_type.value)
        if limit is not None:
            stmt = stmt.limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [m.to_entity() for m in models]

    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
        job_type: JobType | None = None,
    ) -> list[FailedJobGroup]:
        error = func.coalesce(JobModel.error, UNKNOWN_JOB_ERROR)
        stmt = (
            select(
                JobModel.job_type,
                error.label("error"),
                func.count().label("count"),
                func.group_concat(JobModel.source_id).label("source_ids_csv"),
            )
            .where(JobModel.status == JobStatus.FAILED.value)
            .group_by(JobModel.job_type, error)
            .order_by(func.count().desc())
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        if job_type is not None:
            stmt = stmt.where(JobModel.job_type == job_type.value)

        return [
            FailedJobGroup(
                job_type=JobType(row.job_type),
                error=row.error,
                count=row._mapping["count"],
                source_counts=dict(Counter(
                    int(s) for s in str(row.source_ids_csv or "").split(",") if s
                )),
            )
            for row in self._session.execute(stmt).all()
        ]

    # ── Helpers ──────────────────────────────────────────────────────

    def _is_active(self, job_type: str, source_id: int, candidate_id: int | None) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(
                _same_key(job_type, source_id, candidate_id),
                JobModel.status.in_(_ACTIVE_STATUSES),
            )
        )
        return self._session.execute(stmt).scalar_one() > 0

    def _affected(self, stmt: Update | Delete) -> int:
        result: CursorResult[tuple[()]] = self._session.execute(stmt)  # type: ignore[assignment]
        self._session.flush()
        return result.rowcount
