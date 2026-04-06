from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response

from backend.application.dto.generation_dtos import (  # noqa: TC001
    GenerationJobDTO,
    GenerationQueueDTO,
    StartGenerationRequest,
)
from backend.domain.exceptions import GenerationAlreadyRunningError, NoActiveCandidatesError
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/start", status_code=202)
async def start_generation(
    request: StartGenerationRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> GenerationQueueDTO:
    try:
        use_case = container.start_generation_use_case(session)
        queue_dto = use_case.execute(request.source_id)
        session.commit()
    except GenerationAlreadyRunningError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except NoActiveCandidatesError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Launch first job if exists
    if queue_dto.pending_jobs:
        first_job_id = queue_dto.pending_jobs[0].id
        asyncio.create_task(
            _run_generation_background(
                first_job_id, request.source_id, container, session_factory
            )
        )

    return queue_dto


@router.post("/{job_id}/stop")
def stop_generation(
    job_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    use_case = container.stop_generation_use_case(session)
    use_case.execute(job_id)
    session.commit()
    return {"status": "pausing"}


@router.get("/status")
def get_generation_status(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> Response:
    use_case = container.get_generation_status_use_case(session)
    result = use_case.execute()
    if result is None:
        return Response(status_code=204)
    return JSONResponse(content=result.model_dump(mode="json", by_alias=True))


async def _run_generation_background(
    job_id: int,
    source_id: int | None,
    container: Container,
    session_factory: object,
) -> None:
    """Run a generation job and recursively launch the next pending job."""
    bg_session: Session = session_factory()  # type: ignore[operator]
    try:
        use_case = container.run_generation_job_use_case(bg_session)
        await asyncio.to_thread(use_case.execute, job_id, commit=bg_session.commit)
    except Exception:
        bg_session.rollback()
        logger.exception("Generation job %d failed", job_id)
        # Mark job as FAILED in a fresh session
        err_session: Session = session_factory()  # type: ignore[operator]
        try:
            from backend.domain.value_objects.generation_job_status import GenerationJobStatus
            from backend.infrastructure.persistence.sqla_generation_job_repository import (
                SqlaGenerationJobRepository,
            )

            repo = SqlaGenerationJobRepository(err_session)
            job = repo.get_by_id(job_id)
            if job is not None:
                job.status = GenerationJobStatus.FAILED
                repo.update(job)
                err_session.commit()
        except Exception:
            logger.exception("Failed to mark generation job %d as FAILED", job_id)
            err_session.rollback()
        finally:
            err_session.close()
    finally:
        bg_session.close()

    # After current job finishes, check for next pending job
    next_session: Session = session_factory()  # type: ignore[operator]
    try:
        from backend.infrastructure.persistence.sqla_generation_job_repository import (
            SqlaGenerationJobRepository,
        )

        repo = SqlaGenerationJobRepository(next_session)
        next_job = repo.get_next_pending(source_id)
        if next_job is not None and next_job.id is not None:
            next_job_id = next_job.id
        else:
            next_job_id = None
    finally:
        next_session.close()

    # Recursively run next job if exists
    if next_job_id is not None:
        asyncio.create_task(_run_generation_background(next_job_id, source_id, container, session_factory))
