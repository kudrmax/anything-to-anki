from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["media"])


@router.get("/media/{source_id}/{filename}")
async def serve_media_file(
    source_id: int,
    filename: str,
    container: Container = Depends(get_container),  # noqa: B008
) -> FileResponse:
    media_root = container.media_root()
    file_path = os.path.join(media_root, str(source_id), filename)
    if not os.path.exists(file_path):
        await container.lazy_media_reconciler().schedule(source_id)
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)


@router.post("/sources/{source_id}/media-extraction", status_code=202)
async def start_media_extraction(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.start_media_extraction_use_case(session)
    job = use_case.execute(source_id=source_id)
    session.commit()
    asyncio.create_task(_run_media_job_background(job.id, container, session_factory))
    return {"job_id": job.id, "status": job.status.value}


@router.get("/sources/{source_id}/media-extraction/{job_id}")
def get_media_extraction_status(
    source_id: int,
    job_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.get_media_extraction_status_use_case(session)
    job = use_case.execute(job_id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status.value,
        "total": job.total_candidates,
        "processed": job.processed_candidates,
        "failed": job.failed_candidates,
        "skipped": job.skipped_candidates,
    }


async def _run_media_job_background(
    job_id: int,
    container: Container,
    session_factory: object,
) -> None:
    bg_session = session_factory()  # type: ignore[operator]
    try:
        use_case = container.run_media_extraction_job_use_case(bg_session)
        await asyncio.to_thread(use_case.execute, job_id)
        bg_session.commit()
    except Exception:  # noqa: BLE001
        bg_session.rollback()
    finally:
        bg_session.close()
