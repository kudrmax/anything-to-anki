from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.application.dto.candidate_dtos import AddManualCandidateRequest  # noqa: TC001
from backend.application.dto.source_dtos import (  # noqa: TC001
    CreateSourceRequest,
    SourceDetailDTO,
    SourceDTO,
    StoredCandidateDTO,
    UpdateTitleRequest,
)
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceHasActiveJobsError,
    SourceIsProcessingError,
    SourceNotFoundError,
    SourceNotReprocessableError,
)
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", status_code=201)
def create_source(
    request: CreateSourceRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        use_case = container.create_source_use_case(session)
        source = use_case.execute(request.raw_text, request.input_method, request.title)
        session.commit()
        return {"id": source.id, "status": source.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/url", status_code=201)
def create_url_source(
    body: dict[str, Any],
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    from backend.domain.exceptions import SubtitlesNotAvailableError, UnsupportedUrlError

    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    title = body.get("title")

    use_case = container.create_source_from_url_use_case(session)
    try:
        source = use_case.execute(url, title_override=title)
        session.commit()
        return {"id": source.id, "status": source.status.value}
    except SubtitlesNotAvailableError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "subtitles_not_available", "message": str(e)},
        ) from e
    except UnsupportedUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def list_sources(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[SourceDTO]:
    use_case = container.get_sources_use_case(session)
    return use_case.list_all()


@router.get("/{source_id}")
def get_source(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SourceDetailDTO:
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    try:
        sort_order = CandidateSortOrder(sort)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort: {sort}. Use 'relevance' or 'chronological'.",
        ) from e
    try:
        use_case = container.get_sources_use_case(session)
        return use_case.get_by_id(source_id, sort_order=sort_order)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{source_id}/title")
def rename_source(
    source_id: int,
    request: UpdateTitleRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        use_case = container.rename_source_use_case(session)
        use_case.execute(source_id, request.title)
        session.commit()
        return {"id": source_id, "title": request.title.strip()}
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{source_id}/process", status_code=202)
async def process_source(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> dict[str, str]:
    try:
        use_case = container.process_source_use_case(session)
        use_case.start(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceAlreadyProcessedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    asyncio.create_task(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


@router.post("/{source_id}/download-video", status_code=202)
def download_video(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    from datetime import UTC, datetime

    from backend.domain.entities.job import Job
    from backend.domain.value_objects.job_status import JobStatus
    from backend.domain.value_objects.job_type import JobType
    from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

    repo = SqlaSourceRepository(session)
    source = repo.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    if source.source_url is None:
        raise HTTPException(status_code=400, detail="Source has no URL")
    if source.video_path is not None:
        raise HTTPException(status_code=409, detail="Video already downloaded")

    job_repo = container.job_repository(session)
    job_repo.create_bulk([
        Job(
            id=None,
            job_type=JobType.VIDEO_DOWNLOAD,
            candidate_id=None,
            source_id=source_id,
            status=JobStatus.QUEUED,
            error=None,
            created_at=datetime.now(tz=UTC),
            started_at=None,
        ),
    ])
    session.commit()
    return {"status": "downloading"}


async def _process_background(
    source_id: int,
    container: Container,
    session_factory: object,
) -> None:
    bg_session: Session = session_factory()  # type: ignore[operator]
    try:
        use_case = container.process_source_use_case(bg_session)
        await asyncio.to_thread(use_case.execute, source_id, on_stage_commit=bg_session.commit)
        bg_session.commit()
    except Exception:
        logger.exception("Background processing failed (source_id=%d)", source_id)
        bg_session.rollback()
        # Mark source as ERROR in a fresh session
        err_session: Session = session_factory()  # type: ignore[operator]
        try:
            import traceback
            error_detail = traceback.format_exc()
            from backend.infrastructure.persistence.sqla_source_repository import (
                SqlaSourceRepository,
            )
            repo = SqlaSourceRepository(err_session)
            repo.update_status(source_id, SourceStatus.ERROR, error_message=error_detail[-500:])
            err_session.commit()
        except Exception:
            logger.exception("Failed to mark source %d as ERROR", source_id)
            err_session.rollback()
        finally:
            err_session.close()
    finally:
        bg_session.close()


_REVIEW_STATUSES = frozenset({
    SourceStatus.DONE,
    SourceStatus.PARTIALLY_REVIEWED,
    SourceStatus.REVIEWED,
})


@router.patch("/{source_id}/status")
def update_source_status(
    source_id: int,
    body: dict[str, str],
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    raw_status = body.get("status", "")
    try:
        new_status = SourceStatus(raw_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {raw_status}") from None
    if new_status not in _REVIEW_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Status transition to '{raw_status}' not allowed"
        ) from None
    from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
    repo = SqlaSourceRepository(session)
    source = repo.get_by_id(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
    repo.update_status(source_id, new_status)
    session.commit()
    return {"id": source_id, "status": new_status.value}


@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> None:
    try:
        use_case = container.delete_source_use_case(session)
        use_case.execute(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceIsProcessingError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{source_id}/candidates/manual", status_code=201)
def add_manual_candidate(
    source_id: int,
    request: AddManualCandidateRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> StoredCandidateDTO:
    try:
        use_case = container.add_manual_candidate_use_case(session)
        result = use_case.execute(source_id, request.surface_form, request.context_fragment)
        session.commit()
        return result
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/video", status_code=201)
async def create_video_source(
    video: UploadFile = File(...),  # noqa: B008
    srt: UploadFile | None = File(None),  # noqa: B008
    title: str | None = Form(None),  # noqa: B008
    subtitle_track_index: int | None = Form(None),  # noqa: B008
    audio_track_index: int | None = Form(None),  # noqa: B008
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    from backend.application.dto.video_dtos import TrackSelectionRequired

    # Save video to disk
    data_dir = os.getenv("DATA_DIR", ".")
    videos_dir = os.path.join(data_dir, "videos")
    os.makedirs(videos_dir, exist_ok=True)
    ext = os.path.splitext(video.filename or "video.mp4")[1]
    video_filename = f"{uuid.uuid4()}{ext}"
    video_path = os.path.join(videos_dir, video_filename)
    CHUNK_SIZE = 64 * 1024  # 64 KB
    total_bytes = 0
    with open(video_path, "wb") as f:
        while chunk := await video.read(CHUNK_SIZE):
            f.write(chunk)
            total_bytes += len(chunk)
    logger.info(
        "Uploaded video %s (%d bytes) subtitle_track=%s audio_track=%s",
        video_filename, total_bytes, subtitle_track_index, audio_track_index,
    )

    srt_text: str | None = None
    if srt is not None:
        srt_bytes = await srt.read()
        srt_text = srt_bytes.decode("utf-8", errors="replace")

    use_case = container.create_source_use_case(session)
    try:
        result = use_case.execute_video(
            video_path=video_path,
            srt_text=srt_text,
            title=title,
            subtitle_track_index=subtitle_track_index,
            audio_track_index=audio_track_index,
        )
    except ValueError as e:
        os.remove(video_path)
        raise HTTPException(status_code=400, detail=str(e)) from e

    if isinstance(result, TrackSelectionRequired):
        return {
            "status": "track_selection_required",
            "pending_video_path": video_path,
            "subtitle_tracks": [
                {
                    "index": t.index,
                    "language": t.language,
                    "title": t.title,
                    "codec": t.codec,
                }
                for t in result.subtitle_tracks
            ],
            "audio_tracks": [
                {
                    "index": t.index,
                    "language": t.language,
                    "title": t.title,
                    "codec": t.codec,
                    "channels": t.channels,
                }
                for t in result.audio_tracks
            ],
        }

    session.commit()
    return {"id": result.source_id, "status": "new"}


@router.get("/{source_id}/queue-summary")
def get_queue_summary(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, dict[str, int]]:
    """Aggregate counts of jobs by type and status.
    Used by frontend to show 'Cancel queue' / 'Retry failed' button visibility."""
    job_repo = container.job_repository(session)
    return job_repo.get_queue_summary(source_id)


@router.get("/{source_id}/reprocess-stats")
def get_reprocess_stats(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        use_case = container.get_reprocess_stats_use_case(session)
        stats = use_case.execute(source_id)
        return {
            "learn_count": stats.learn_count,
            "known_count": stats.known_count,
            "skip_count": stats.skip_count,
            "pending_count": stats.pending_count,
            "has_active_jobs": stats.has_active_jobs,
        }
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{source_id}/reprocess", status_code=202)
async def reprocess_source(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> dict[str, str]:
    try:
        use_case = container.reprocess_source_use_case(session)
        use_case.execute(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceNotReprocessableError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SourceHasActiveJobsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    asyncio.create_task(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


@router.get("/{source_id}/candidates")
def get_candidates(
    source_id: int,
    sort: str = "relevance",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[dict[str, Any]]:
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    try:
        sort_order = CandidateSortOrder(sort)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort: {sort}. Use 'relevance' or 'chronological'.",
        ) from e
    try:
        use_case = container.get_candidates_use_case(session)
        candidates = use_case.execute(source_id, sort_order=sort_order)
        return [c.model_dump() for c in candidates]
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
