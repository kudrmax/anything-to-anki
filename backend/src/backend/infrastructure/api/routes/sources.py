from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Response

from backend.application.dto.add_source_dtos import (
    AddSourceRequest,
    CreateTopicRequest,
    DetectedFormatDTO,
    DetectFormatRequest,
    QuestionsRequired,
    SourcesCreated,
)
from backend.application.dto.candidate_dtos import (  # noqa: TC001
    AddManualCandidateRequest,
    AddSavedPhraseRequest,
)
from backend.application.dto.collection_dtos import (  # noqa: TC001
    DeletedSourcesDTO,
    PlacedSourcesDTO,
    PlaceSourcesRequest,
    SourceIdsRequest,
    StartedSourcesDTO,
)
from backend.application.dto.document_dtos import SourceDocumentDTO  # noqa: TC001
from backend.application.dto.source_dtos import (  # noqa: TC001
    SourceBoardDTO,
    SourceDetailDTO,
    SourceDTO,
    StoredCandidateDTO,
    UpdateTitleRequest,
)
from backend.application.source_intake.typed_input import typed_input
from backend.domain.exceptions import (
    BookReadError,
    CollectionNotFoundError,
    InvalidAnswerError,
    InvalidPhraseError,
    InvalidSourceInputError,
    NotATextFileError,
    PermanentSourceError,
    SourceAlreadyProcessedError,
    SourceHasActiveJobsError,
    SourceHasNoDocumentError,
    SourceHasNoUrlError,
    SourceIsProcessingError,
    SourceNotFoundError,
    SourceNotReprocessableError,
    SubtitlesNotAvailableError,
    TopicTargetsMissingError,
    UnsupportedUrlError,
    VideoAlreadyDownloadedError,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.api.scope_param import parse_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/add", status_code=201)
def add_source(
    request: AddSourceRequest,
    response: Response,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QuestionsRequired | SourcesCreated:
    """Pasted text, a file path or a link. Questions come back until every one is answered."""
    try:
        result = container.add_source_use_case(session).execute(
            typed_input(request.text, request.subtitles_path),
            request.title,
            Answers(request.answers),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SubtitlesNotAvailableError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "subtitles_not_available", "message": str(e)},
        ) from e
    except (
        InvalidSourceInputError,
        InvalidAnswerError,
        BookReadError,
        NotATextFileError,
        UnsupportedUrlError,
    ) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if isinstance(result, QuestionsRequired):
        response.status_code = 200
        return result
    session.commit()
    return result


@router.post("/detect-format")
def detect_format(
    request: DetectFormatRequest,
    container: Container = Depends(get_container),  # noqa: B008
) -> DetectedFormatDTO:
    """The hint under the input field: how what the user put there will be read."""
    try:
        return container.detect_format_use_case().execute(typed_input(request.text))
    except InvalidSourceInputError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/topic", status_code=201)
def create_topic(
    request: CreateTopicRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        source = container.create_topic_use_case(session).execute(request.query, request.title)
    except InvalidSourceInputError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    session.commit()
    return {"id": source.id, "status": source.status.value}


@router.post("/saved-phrases", status_code=201)
def add_saved_phrase(
    request: AddSavedPhraseRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> StoredCandidateDTO:
    try:
        use_case = container.add_saved_phrase_use_case(session)
        result = use_case.execute(request.phrase, request.target_words)
        session.commit()
        return result
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def list_sources(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[SourceDTO]:
    use_case = container.get_sources_use_case(session)
    return use_case.list_all()


@router.get("/board")
def get_source_board(
    scope: str = "all",
    query: str = "",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SourceBoardDTO:
    try:
        return container.get_sources_use_case(session).board(parse_scope(scope), query)
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/placements")
def place_sources(
    request: PlaceSourcesRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> PlacedSourcesDTO:
    try:
        result = container.place_sources_use_case(session).execute(request.placements)
        session.commit()
        return result
    except (SourceNotFoundError, CollectionNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/process-pending", status_code=202)
async def process_pending(
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> StartedSourcesDTO:
    use_case = container.process_sources_use_case(session)
    try:
        result = use_case.start(use_case.pending_in(parse_scope(scope)))
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    session.commit()
    _launch(result.started, container, session_factory)
    return result


@router.post("/process-batch", status_code=202)
async def process_batch(
    request: SourceIdsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> StartedSourcesDTO:
    result = container.process_sources_use_case(session).start(
        list(dict.fromkeys(request.source_ids)),
    )
    session.commit()
    _launch(result.started, container, session_factory)
    return result


@router.post("/delete-batch")
def delete_batch(
    request: SourceIdsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> DeletedSourcesDTO:
    result = container.delete_sources_use_case(session).execute(
        list(dict.fromkeys(request.source_ids)),
    )
    session.commit()
    return result


def _launch(source_ids: list[int], container: Container, session_factory: object) -> None:
    for source_id in source_ids:
        asyncio.create_task(_process_background(source_id, container, session_factory))


@router.get("/{source_id}")
def get_source(
    source_id: int,
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SourceDetailDTO:
    try:
        use_case = container.get_sources_use_case(session)
        return use_case.get_by_id(source_id, sort_order=sort)
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
    except (SourceAlreadyProcessedError, TopicTargetsMissingError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    asyncio.create_task(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


@router.post("/{source_id}/download-video", status_code=202)
def download_video(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    try:
        container.request_video_download_use_case(session).execute(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceHasNoUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except VideoAlreadyDownloadedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
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
        # Restore enrichment from cache (best-effort, uses bg_session)
        reprocess_uc = container.reprocess_source_use_case(bg_session)
        reprocess_uc.finalize(source_id)
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
    except (SourceIsProcessingError, PermanentSourceError) as e:
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
        result = use_case.execute(source_id, request.target_words, request.selection)
        session.commit()
        return result
    except (SourceNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{source_id}/document")
def get_source_document(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SourceDocumentDTO:
    """The text of the source as its screen shows it, with the targets to mark."""
    try:
        return container.get_source_document_use_case(session).execute(source_id)
    except SourceHasNoDocumentError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
    except (SourceHasActiveJobsError, TopicTargetsMissingError, PermanentSourceError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    asyncio.create_task(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


@router.get("/{source_id}/candidates")
def get_candidates(
    source_id: int,
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[dict[str, Any]]:
    try:
        use_case = container.get_candidates_use_case(session)
        candidates = use_case.execute(source_id, sort_order=sort)
        return [c.model_dump() for c in candidates]
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
