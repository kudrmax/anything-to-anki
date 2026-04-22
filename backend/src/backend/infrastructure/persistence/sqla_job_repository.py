from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CursorResult, delete, func, select, update

from backend.domain.ports.job_repository import JobRepository
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.persistence.models import JobModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.job import Job


class SqlaJobRepository(JobRepository):
    """SQLAlchemy implementation of JobRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_bulk(self, jobs: list[Job]) -> list[Job]:
        models = [JobModel.from_entity(j) for j in jobs]
        self._session.add_all(models)
        self._session.flush()
        return [m.to_entity() for m in models]

    def dequeue_next(self) -> Job | None:
        stmt = (
            select(JobModel)
            .where(JobModel.status == JobStatus.QUEUED.value)
            .order_by(JobModel.created_at.asc(), JobModel.id.asc())
            .limit(1)
            .with_for_update()
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        model.status = JobStatus.RUNNING.value
        model.started_at = datetime.now(tz=UTC)
        self._session.flush()
        return model.to_entity()

    def dequeue_batch(
        self, job_type: JobType, source_id: int, limit: int,
    ) -> list[Job]:
        stmt = (
            select(JobModel)
            .where(
                JobModel.status == JobStatus.QUEUED.value,
                JobModel.job_type == job_type.value,
                JobModel.source_id == source_id,
            )
            .order_by(JobModel.created_at.asc(), JobModel.id.asc())
            .limit(limit)
            .with_for_update()
        )
        models = list(self._session.execute(stmt).scalars().all())
        now = datetime.now(tz=UTC)
        for m in models:
            m.status = JobStatus.RUNNING.value
            m.started_at = now
        self._session.flush()
        return [m.to_entity() for m in models]

    def mark_failed(self, job_id: int, error: str) -> None:
        self._session.execute(
            update(JobModel)
            .where(JobModel.id == job_id)
            .values(status=JobStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def mark_failed_bulk(self, job_ids: list[int], error: str) -> None:
        if not job_ids:
            return
        self._session.execute(
            update(JobModel)
            .where(JobModel.id.in_(job_ids))
            .values(status=JobStatus.FAILED.value, error=error)
        )
        self._session.flush()

    def delete(self, job_id: int) -> None:
        self._session.execute(
            delete(JobModel).where(JobModel.id == job_id)
        )
        self._session.flush()

    def delete_bulk(self, job_ids: list[int]) -> None:
        if not job_ids:
            return
        self._session.execute(
            delete(JobModel).where(JobModel.id.in_(job_ids))
        )
        self._session.flush()

    def delete_by_source_and_type(
        self, source_id: int, job_type: JobType,
    ) -> int:
        stmt = (
            delete(JobModel)
            .where(
                JobModel.source_id == source_id,
                JobModel.job_type == job_type.value,
                JobModel.status.in_([
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ]),
            )
        )
        result: CursorResult[tuple[()]] = self._session.execute(stmt)  # type: ignore[assignment]
        self._session.flush()
        return result.rowcount

    def delete_failed_by_source_and_type(
        self, source_id: int, job_type: JobType,
    ) -> list[Job]:
        # First select the failed jobs to return them
        select_stmt = (
            select(JobModel)
            .where(
                JobModel.source_id == source_id,
                JobModel.job_type == job_type.value,
                JobModel.status == JobStatus.FAILED.value,
            )
        )
        models = list(self._session.execute(select_stmt).scalars().all())
        entities = [m.to_entity() for m in models]
        # Then delete them
        if models:
            delete_stmt = (
                delete(JobModel)
                .where(
                    JobModel.source_id == source_id,
                    JobModel.job_type == job_type.value,
                    JobModel.status == JobStatus.FAILED.value,
                )
            )
            self._session.execute(delete_stmt)
            self._session.flush()
        return entities

    def fail_all_running(self, error: str) -> int:
        count_stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(JobModel.status == JobStatus.RUNNING.value)
        )
        count: int = self._session.execute(count_stmt).scalar_one()
        if count:
            self._session.execute(
                update(JobModel)
                .where(JobModel.status == JobStatus.RUNNING.value)
                .values(status=JobStatus.FAILED.value, error=error)
            )
            self._session.flush()
        return count

    def job_exists(self, job_id: int) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(JobModel.id == job_id)
        )
        return self._session.execute(stmt).scalar_one() > 0

    def has_active_jobs_for_source(
        self, source_id: int, job_types: frozenset[JobType] | None = None,
    ) -> bool:
        stmt = (
            select(func.count())
            .select_from(JobModel)
            .where(
                JobModel.source_id == source_id,
                JobModel.status.in_([
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ]),
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

    def get_source_ids_with_active_jobs(
        self, job_type: JobType,
    ) -> list[int]:
        stmt = (
            select(JobModel.source_id)
            .where(
                JobModel.job_type == job_type.value,
                JobModel.status.in_([
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ]),
            )
            .distinct()
        )
        return list(self._session.execute(stmt).scalars().all())

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
            .order_by(JobModel.created_at.asc(), JobModel.id.asc())
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
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                JobModel.job_type,
                JobModel.error,
                func.count().label("count"),
                func.group_concat(JobModel.source_id).label("source_ids_csv"),
                func.group_concat(JobModel.candidate_id).label("candidate_ids_csv"),
            )
            .where(JobModel.status == JobStatus.FAILED.value)
            .group_by(JobModel.job_type, JobModel.error)
            .order_by(func.count().desc())
        )
        if source_id is not None:
            stmt = stmt.where(JobModel.source_id == source_id)
        if job_type is not None:
            stmt = stmt.where(JobModel.job_type == job_type.value)

        rows = self._session.execute(stmt).all()
        result: list[dict[str, Any]] = []
        for row in rows:
            source_ids_raw = str(row.source_ids_csv or "")
            candidate_ids_raw = str(row.candidate_ids_csv or "")
            source_ids = sorted({int(s) for s in source_ids_raw.split(",") if s})
            candidate_ids = [int(c) for c in candidate_ids_raw.split(",") if c]
            result.append({
                "job_type": row.job_type,
                "error": row.error or "Unknown error",
                "count": row.count,
                "source_ids": source_ids,
                "candidate_ids": candidate_ids,
            })
        return result
