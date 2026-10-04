from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import get_container, get_db_session
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["tts"])


@router.post("/candidates/{candidate_id}/generate-tts", status_code=202)
def enqueue_candidate_tts(
    candidate_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    """Enqueue TTS generation for a single candidate (any source type)."""
    candidate_repo = SqlaCandidateRepository(session)
    candidate = candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    now = datetime.now(tz=UTC)
    job_repo = container.job_repository(session)
    job_repo.create_bulk([
        Job(
            id=None,
            job_type=JobType.TTS,
            candidate_id=candidate_id,
            source_id=candidate.source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=now,
            started_at=None,
        )
    ])
    session.commit()
    return {"status": "enqueued"}
