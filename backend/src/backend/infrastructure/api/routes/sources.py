from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, sessionmaker  # noqa: TC002 — FastAPI reads route annotations

from backend.application.dto.add_source_dtos import (
    AddSourceRequest,
    CollectionChoiceDTO,
    CreateTopicRequest,
    DescribeInputRequest,
    InputDescriptionDTO,
    NamingDTO,
    NamingRequired,
    QuestionsRequired,
    RenderNamesRequest,
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
from backend.application.dto.source_dtos import (  # noqa: TC001
    CardDTO,
    SourceBoardDTO,
    SourceDTO,
    UpdateTitleRequest,
)
from backend.application.source_intake.naming import Naming
from backend.application.source_intake.typed_input import typed_inputs
from backend.domain.exceptions import (
    BookReadError,
    CollectionNotFoundError,
    InputFailedError,
    InvalidAnswerError,
    InvalidPhraseError,
    InvalidSourceInputError,
    NotATextFileError,
    PermanentSourceError,
    SourceAlreadyProcessedError,
    SourceHasNoDocumentError,
    SourceIsProcessingError,
    SourceNotFoundError,
    SourceOperationBusyError,
    SubtitlesNotAvailableError,
    TopicTargetsMissingError,
    UnsupportedUrlError,
)
from backend.domain.value_objects.collection_choice import CollectionChoice
from backend.domain.value_objects.naming_rule import NamingRule
from backend.domain.value_objects.number_format import NumberFormat
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.background import free_source, in_background
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.api.scope_param import parse_scope

if TYPE_CHECKING:
    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/add", status_code=201)
def add_source(
    request: AddSourceRequest,
    response: Response,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> QuestionsRequired | NamingRequired | SourcesCreated:
    """Pasted text, file paths or a link. Questions come back until every one is answered;
    several sources ask how to name them."""
    try:
        naming = _naming(request.naming)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e
    try:
        result = container.add_source_use_case(session).execute(
            typed_inputs(request.text, request.subtitles_path),
            request.title,
            [Answers(answers) for answers in request.answers],
            naming,
        )
    except InputFailedError as e:
        raise _intake_error(e.cause, str(e)) from e
    except _INTAKE_ERRORS as e:
        raise _intake_error(e, str(e)) from e
    if isinstance(result, QuestionsRequired | NamingRequired):
        response.status_code = 200
        return result
    session.commit()
    return result


@router.post("/render-names")
def render_names(
    request: RenderNamesRequest,
    container: Container = Depends(get_container),  # noqa: B008
) -> list[str]:
    """The titles a naming rule gives the sources of one add, for the naming window."""
    try:
        return container.render_names_use_case().execute(
            request.rule, request.collection_name, request.own_titles, request.number_digits,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e


_INTAKE_ERRORS: tuple[type[Exception], ...] = (
    FileNotFoundError,
    SubtitlesNotAvailableError,
    InvalidSourceInputError,
    InvalidAnswerError,
    BookReadError,
    NotATextFileError,
    UnsupportedUrlError,
)


def _intake_error(cause: Exception, message: str) -> HTTPException:
    if isinstance(cause, FileNotFoundError):
        return HTTPException(status_code=404, detail=message)
    if isinstance(cause, SubtitlesNotAvailableError):
        return HTTPException(
            status_code=422,
            detail={"error": "subtitles_not_available", "message": message},
        )
    return HTTPException(status_code=400, detail=message)


def _naming(dto: NamingDTO | None) -> Naming | None:
    if dto is None:
        return None
    collection = dto.collection or CollectionChoiceDTO()
    return Naming(
        collection=CollectionChoice(
            existing_id=collection.existing_id, new_name=collection.new_name,
        ),
        rule=NamingRule(dto.rule),
        titles=dto.titles,
        number_format=NumberFormat(dto.number_digits),
    )


@router.post("/describe-input")
def describe_input(
    request: DescribeInputRequest,
    container: Container = Depends(get_container),  # noqa: B008
) -> InputDescriptionDTO:
    """What the Add screen input becomes: a source, a topic or a phrase, or why it can't be."""
    return container.describe_input_use_case().execute(request.text)


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
) -> CardDTO:
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
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
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
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
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


def _launch(
    source_ids: list[int], container: Container, session_factory: sessionmaker[Session],
) -> None:
    for source_id in source_ids:
        in_background(_process_background(source_id, container, session_factory))


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
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> dict[str, str]:
    try:
        use_case = container.process_source_use_case(session)
        use_case.start(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (
        SourceAlreadyProcessedError, SourceOperationBusyError, TopicTargetsMissingError,
    ) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    in_background(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


async def _process_background(
    source_id: int,
    container: Container,
    session_factory: sessionmaker[Session],
) -> None:
    entered = False
    bg_session: Session | None = None
    try:
        bg_session = session_factory()
        use_case = container.process_source_use_case(bg_session)
        entered = True
        await asyncio.to_thread(use_case.execute, source_id)
        bg_session.commit()
    except Exception:
        logger.exception("Background processing failed (source_id=%d)", source_id)
        if bg_session is not None:
            bg_session.rollback()
        if not entered:
            free_source(source_id, session_factory)
        # Mark source as ERROR in a fresh session
        err_session: Session = session_factory()
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
        if bg_session is not None:
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
) -> CardDTO:
    try:
        use_case = container.add_manual_candidate_use_case(session)
        result = use_case.execute(source_id, request.target_words, request.selection)
        session.commit()
        return result
    except (SourceNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
