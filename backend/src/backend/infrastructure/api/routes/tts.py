from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.domain.entities.job import Job
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.api.dependencies import get_container, get_db_session

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["tts"])


@router.post("/sources/{source_id}/tts/generate", status_code=202)
def enqueue_tts_generation(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Enqueue TTS generation jobs for all eligible candidates."""
    use_case = container.enqueue_tts_generation_use_case(session)
    eligible_ids = use_case.execute(source_id)
    session.commit()
    return {"enqueued": len(eligible_ids)}


@router.post("/sources/{source_id}/tts/cancel")
def cancel_tts_queue(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued and running TTS generation jobs."""
    job_repo = container.job_repository(session)
    cancelled = job_repo.delete_by_source_and_type(source_id, JobType.TTS)
    session.commit()
    return {"cancelled": cancelled}


@router.post("/sources/{source_id}/tts/retry-failed", status_code=202)
def retry_failed_tts(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Re-enqueue all FAILED TTS jobs."""
    job_repo = container.job_repository(session)
    failed_jobs = job_repo.delete_failed_by_source_and_type(source_id, JobType.TTS)
    if not failed_jobs:
        return {"enqueued": 0}

    now = datetime.now(tz=UTC)
    new_jobs = [
        Job(
            id=None,
            job_type=JobType.TTS,
            candidate_id=j.candidate_id,
            source_id=source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=now,
            started_at=None,
        )
        for j in failed_jobs
    ]
    job_repo.create_bulk(new_jobs)
    session.commit()
    return {"enqueued": len(new_jobs)}
