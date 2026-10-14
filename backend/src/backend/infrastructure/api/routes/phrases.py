"""Actions on a card: a phrase of a word."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO  # noqa: TC001
from backend.application.dto.candidate_dtos import (  # noqa: TC001
    DecidePhraseRequest,
    EditPhraseRequest,
    ReplaceWithExampleRequest,
    RevertPolishRequest,
    SetPhraseBoundaryRequest,
)
from backend.application.dto.card_report_dtos import (  # noqa: TC001
    CardReportDTO,
    ReportCandidateRequest,
)
from backend.application.dto.cloze_dtos import (  # noqa: TC001
    ClozePreviewDTO,
    PreviewClozeRequest,
    SaveClozeRequest,
)
from backend.application.dto.follow_up_dtos import FollowUpRequest  # noqa: TC001
from backend.application.dto.source_dtos import CardDTO  # noqa: TC001
from backend.domain.exceptions import (
    AIServiceError,
    AlreadyInAnkiError,
    CandidateNotPolishedError,
    CardDecisionLockedError,
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    DecidedElsewhereError,
    EmptyReportCommentError,
    InvalidClozeError,
    InvalidPhraseError,
    PhraseChangedError,
    PhraseNotFoundError,
    PhrasePolishNotSupportedError,
    SourceHasNoDocumentError,
    SourceOperationBusyError,
    UnknownReportReasonError,
)
from backend.domain.services.card_decision import DecisionAction
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/phrases", tags=["phrases"])

# A Rebuild or a refresh holds the source: no card changes by hand meanwhile.
REFUSED_DECISIONS = (
    AlreadyInAnkiError, CardDecisionLockedError, DecidedElsewhereError, ClozeNotAllowedError,
    SourceOperationBusyError,
)
# The source is busy with a long operation, or one changed the phrase meanwhile.
REFUSED_GENERATION = (SourceOperationBusyError, PhraseChangedError)


@router.put("/{phrase_id}/decision")
def decide_phrase(
    phrase_id: int,
    request: DecidePhraseRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        container.decide_phrase_use_case(session).execute(
            phrase_id, DecisionAction(request.status),
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_DECISIONS as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    session.commit()
    return {"id": phrase_id, "status": request.status}


@router.put("/{phrase_id}/cloze")
def save_cloze(
    phrase_id: int,
    request: SaveClozeRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CardDTO:
    try:
        candidate = container.save_cloze_use_case(session).execute(
            phrase_id,
            request.phrase,
            request.hidden_word_indices,
            ClozeHintKind(request.hint_kind),
            request.custom_hint,
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (*REFUSED_DECISIONS, ClozePhraseChangedError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidClozeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    session.commit()
    return candidate


@router.post("/{phrase_id}/cloze/preview")
def preview_cloze(
    phrase_id: int,
    request: PreviewClozeRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> ClozePreviewDTO:
    try:
        return container.preview_cloze_use_case(session).execute(phrase_id, request)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidClozeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/{phrase_id}/report", status_code=201)
def report_phrase(
    phrase_id: int,
    request: ReportCandidateRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CardReportDTO:
    try:
        report = container.report_candidate_use_case(session).execute(phrase_id, request)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (EmptyReportCommentError, UnknownReportReasonError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    session.commit()
    return report


@router.put("/{phrase_id}/polish/reverted")
def revert_phrase_polish(
    phrase_id: int,
    request: RevertPolishRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        container.revert_phrase_polish_use_case(session).execute(phrase_id, request.reverted)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (CandidateNotPolishedError, SourceOperationBusyError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    session.commit()
    return {"id": phrase_id, "reverted": request.reverted}


@router.put("/{phrase_id}/phrase")
def edit_phrase(
    phrase_id: int,
    request: EditPhraseRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    """The text of the card's phrase, rewritten by hand."""
    try:
        container.edit_card_phrase_use_case(session).execute(phrase_id, request.phrase)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    session.commit()
    return {"id": phrase_id}


@router.put("/{phrase_id}/phrase-boundary")
def set_phrase_boundary(
    phrase_id: int,
    request: SetPhraseBoundaryRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    """The phrase of a card, selected anew on the source screen."""
    try:
        phrase = container.set_phrase_boundary_use_case(session).execute(
            phrase_id, request.selection,
        )
    except (PhraseNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    session.commit()
    return {"id": phrase_id, "context_fragment": phrase}


@router.post("/{phrase_id}/replace-with-example", status_code=201)
def replace_with_example(
    phrase_id: int,
    request: ReplaceWithExampleRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CardDTO:
    try:
        result = container.replace_with_example_use_case(session).execute(
            phrase_id, request.example_text,
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (AlreadyInAnkiError, SourceOperationBusyError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    session.commit()
    return result


@router.post("/{phrase_id}/polish", status_code=202)
def polish_phrase_again(
    phrase_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    try:
        container.enqueue_phrase_polish_use_case(session).execute(phrase_id)
        session.commit()
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PhrasePolishNotSupportedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"status": "queued"}


@router.post("/{phrase_id}/generate-tts", status_code=202)
def enqueue_phrase_tts(
    phrase_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    """Enqueue TTS generation for one phrase (any source type)."""
    try:
        container.enqueue_phrase_tts_use_case(session).execute(phrase_id)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    session.commit()
    return {"status": "enqueued"}


@router.post("/{phrase_id}/regenerate-media", status_code=202)
def regenerate_phrase_media(
    phrase_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    try:
        container.regenerate_phrase_media_use_case(session).execute(phrase_id)
        session.commit()
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "regenerated"}


@router.post("/{phrase_id}/generate-meaning")
async def generate_meaning(
    phrase_id: int,
    follow_up: FollowUpRequest | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GenerateMeaningResponseDTO:
    try:
        use_case = container.generate_meaning_use_case(session)
        if follow_up is not None:
            result = await asyncio.to_thread(
                use_case.execute_follow_up, phrase_id, follow_up.action, follow_up.text,
            )
        else:
            result = await asyncio.to_thread(use_case.execute, phrase_id)
        session.commit()
        return result
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except AIServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
