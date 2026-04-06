from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.generation_job_repository import GenerationJobRepository
from backend.domain.value_objects.generation_job_status import GenerationJobStatus
from backend.infrastructure.persistence.models import GenerationJobModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.generation_job import GenerationJob


class SqlaGenerationJobRepository(GenerationJobRepository):
    """SQLAlchemy implementation of GenerationJobRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, job: GenerationJob) -> GenerationJob:
        model = GenerationJobModel.from_entity(job)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, job_id: int) -> GenerationJob | None:
        model = self._session.get(GenerationJobModel, job_id)
        return model.to_entity() if model else None

    def get_running(self) -> GenerationJob | None:
        model = (
            self._session.query(GenerationJobModel)
            .filter(GenerationJobModel.status == GenerationJobStatus.RUNNING.value)
            .first()
        )
        return model.to_entity() if model else None

    def get_pending(self) -> list[GenerationJob]:
        models = (
            self._session.query(GenerationJobModel)
            .filter(GenerationJobModel.status == GenerationJobStatus.PENDING.value)
            .order_by(GenerationJobModel.created_at)
            .all()
        )
        return [m.to_entity() for m in models]

    def get_next_pending(self, source_id: int | None) -> GenerationJob | None:
        query = self._session.query(GenerationJobModel).filter(
            GenerationJobModel.status == GenerationJobStatus.PENDING.value
        )
        if source_id is not None:
            query = query.filter(GenerationJobModel.source_id == source_id)
        else:
            query = query.filter(GenerationJobModel.source_id.is_(None))
        model = query.order_by(GenerationJobModel.created_at).first()
        return model.to_entity() if model else None

    def cancel_pending_for_source(self, source_id: int | None) -> None:
        from sqlalchemy import update as sqla_update
        stmt = sqla_update(GenerationJobModel).where(
            GenerationJobModel.status == GenerationJobStatus.PENDING.value,
            (GenerationJobModel.source_id == source_id)
            if source_id is not None
            else (GenerationJobModel.source_id.is_(None)),
        ).values(status=GenerationJobStatus.CANCELLED.value)
        self._session.execute(stmt)
        self._session.flush()

    def update(self, job: GenerationJob) -> None:
        import json
        model = self._session.get(GenerationJobModel, job.id)
        if model is not None:
            model.source_id = job.source_id
            model.status = job.status.value
            model.total_candidates = job.total_candidates
            model.candidate_ids_json = json.dumps(job.candidate_ids)
            model.processed_candidates = job.processed_candidates
            model.failed_candidates = job.failed_candidates
            model.skipped_candidates = job.skipped_candidates
            self._session.flush()
