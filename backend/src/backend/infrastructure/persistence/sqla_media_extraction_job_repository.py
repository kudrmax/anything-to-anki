from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.domain.ports.media_extraction_job_repository import MediaExtractionJobRepository
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus
from backend.infrastructure.persistence.models import MediaExtractionJobModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from backend.domain.entities.media_extraction_job import MediaExtractionJob


class SqlaMediaExtractionJobRepository(MediaExtractionJobRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, job: MediaExtractionJob) -> MediaExtractionJob:
        model = MediaExtractionJobModel.from_entity(job)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, job_id: int) -> MediaExtractionJob | None:
        model = self._session.get(MediaExtractionJobModel, job_id)
        return model.to_entity() if model else None

    def get_running(self) -> MediaExtractionJob | None:
        model = (
            self._session.query(MediaExtractionJobModel)
            .filter(MediaExtractionJobModel.status == MediaExtractionJobStatus.RUNNING.value)
            .first()
        )
        return model.to_entity() if model else None

    def update(self, job: MediaExtractionJob) -> None:
        model = self._session.get(MediaExtractionJobModel, job.id)
        if model is not None:
            model.status = job.status.value
            model.processed_candidates = job.processed_candidates
            model.failed_candidates = job.failed_candidates
            model.skipped_candidates = job.skipped_candidates
            model.candidate_ids_json = json.dumps(job.candidate_ids)
            self._session.flush()
