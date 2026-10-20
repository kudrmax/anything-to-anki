from __future__ import annotations

import asyncio
import logging
import traceback
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Response

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
from backend.infrastructure.api.background import in_background
from backend.infrastructure.api.dependencies import (
    DetachedUseCases,
    get_container,
    get_detached_use_cases,
    use_case,
)
from backend.infrastructure.api.scope_param import parse_scope
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.add_manual_candidate import AddManualCandidateUseCase
    from backend.application.use_cases.add_saved_phrase import AddSavedPhraseUseCase
    from backend.application.use_cases.add_source import AddSourceUseCase
    from backend.application.use_cases.create_topic import CreateTopicUseCase
    from backend.application.use_cases.delete_source import DeleteSourceUseCase
    from backend.application.use_cases.delete_sources import DeleteSourcesUseCase
    from backend.application.use_cases.get_sources import GetSourcesUseCase
    from backend.application.use_cases.place_sources import PlaceSourcesUseCase
    from backend.application.use_cases.process_source import ProcessSourceUseCase
    from backend.application.use_cases.process_sources import ProcessSourcesUseCase
    from backend.application.use_cases.rename_source import RenameSourceUseCase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])

# The tail of the traceback a failed processing leaves on its source.
ERROR_DETAIL_LENGTH = 500


@router.post("/add", status_code=201)
def add_source(
    request: AddSourceRequest,
    response: Response,
    add: AddSourceUseCase = Depends(use_case(Container.add_source_use_case)),  # noqa: B008
) -> QuestionsRequired | NamingRequired | SourcesCreated:
    """Pasted text, file paths or a link. Questions come back until every one is answered;
    several sources ask how to name them."""
    try:
        naming = _naming(request.naming)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"message": str(e)}) from e
    try:
        result = add.execute(
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
    create: CreateTopicUseCase = Depends(use_case(Container.create_topic_use_case)),  # noqa: B008
) -> dict[str, Any]:
    try:
        source = create.execute(request.query, request.title)
    except InvalidSourceInputError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": source.id, "status": source.status.value}


@router.post("/saved-phrases", status_code=201)
def add_saved_phrase(
    request: AddSavedPhraseRequest,
    save: AddSavedPhraseUseCase = Depends(  # noqa: B008
        use_case(Container.add_saved_phrase_use_case),  # noqa: B008
    ),
) -> CardDTO:
    try:
        result = save.execute(request.phrase, request.target_words)
        return result
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def list_sources(
    sources: GetSourcesUseCase = Depends(use_case(Container.get_sources_use_case)),  # noqa: B008
) -> list[SourceDTO]:
    return sources.list_all()


@router.get("/board")
def get_source_board(
    scope: str = "all",
    query: str = "",
    sources: GetSourcesUseCase = Depends(use_case(Container.get_sources_use_case)),  # noqa: B008
) -> SourceBoardDTO:
    try:
        return sources.board(parse_scope(scope), query)
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/placements")
def place_sources(
    request: PlaceSourcesRequest,
    place: PlaceSourcesUseCase = Depends(use_case(Container.place_sources_use_case)),  # noqa: B008
) -> PlacedSourcesDTO:
    try:
        result = place.execute(request.placements)
        return result
    except (SourceNotFoundError, CollectionNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/process-pending", status_code=202)
async def process_pending(
    scope: str = "all",
    process: ProcessSourcesUseCase = Depends(  # noqa: B008
        use_case(Container.process_sources_use_case),  # noqa: B008
    ),
    detached: DetachedUseCases = Depends(get_detached_use_cases),  # noqa: B008
) -> StartedSourcesDTO:
    try:
        result = process.start(process.pending_in(parse_scope(scope)))
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    _launch(result.started, detached)
    return result


@router.post("/process-batch", status_code=202)
async def process_batch(
    request: SourceIdsRequest,
    process: ProcessSourcesUseCase = Depends(  # noqa: B008
        use_case(Container.process_sources_use_case),  # noqa: B008
    ),
    detached: DetachedUseCases = Depends(get_detached_use_cases),  # noqa: B008
) -> StartedSourcesDTO:
    result = process.start(list(dict.fromkeys(request.source_ids)))
    _launch(result.started, detached)
    return result


@router.post("/delete-batch")
def delete_batch(
    request: SourceIdsRequest,
    delete: DeleteSourcesUseCase = Depends(  # noqa: B008
        use_case(Container.delete_sources_use_case),  # noqa: B008
    ),
) -> DeletedSourcesDTO:
    return delete.execute(list(dict.fromkeys(request.source_ids)))


def _launch(source_ids: list[int], detached: DetachedUseCases) -> None:
    for source_id in source_ids:
        in_background(_process_background(source_id, detached))


@router.patch("/{source_id}/title")
def rename_source(
    source_id: int,
    request: UpdateTitleRequest,
    rename: RenameSourceUseCase = Depends(  # noqa: B008
        use_case(Container.rename_source_use_case),  # noqa: B008
    ),
) -> dict[str, Any]:
    try:
        rename.execute(source_id, request.title)
        return {"id": source_id, "title": request.title.strip()}
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{source_id}/process", status_code=202)
async def process_source(
    source_id: int,
    process: ProcessSourceUseCase = Depends(  # noqa: B008
        use_case(Container.process_source_use_case),  # noqa: B008
    ),
    detached: DetachedUseCases = Depends(get_detached_use_cases),  # noqa: B008
) -> dict[str, str]:
    try:
        process.start(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (
        SourceAlreadyProcessedError, SourceOperationBusyError, TopicTargetsMissingError,
    ) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    in_background(_process_background(source_id, detached))
    return {"status": "processing"}


async def _process_background(source_id: int, detached: DetachedUseCases) -> None:
    ran = False
    try:
        with detached.open(Container.process_source_use_case) as process:
            ran = True
            await asyncio.to_thread(process.execute, source_id)
    except Exception:
        logger.exception("Background processing failed (source_id=%d)", source_id)
        error = traceback.format_exc()[-ERROR_DETAIL_LENGTH:]
        try:
            with detached.open(Container.process_source_use_case) as process:
                process.fail(source_id, error, never_ran=not ran)
        except Exception:
            logger.exception("Failed to mark source %d as ERROR", source_id)


@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: int,
    delete: DeleteSourceUseCase = Depends(  # noqa: B008
        use_case(Container.delete_source_use_case),  # noqa: B008
    ),
) -> None:
    try:
        delete.execute(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (SourceIsProcessingError, PermanentSourceError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{source_id}/candidates/manual", status_code=201)
def add_manual_candidate(
    source_id: int,
    request: AddManualCandidateRequest,
    add_manual: AddManualCandidateUseCase = Depends(  # noqa: B008
        use_case(Container.add_manual_candidate_use_case),  # noqa: B008
    ),
) -> CardDTO:
    try:
        result = add_manual.execute(source_id, request.target_words, request.selection)
        return result
    except (SourceNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
