"""Actions on a card: a phrase of a word."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO  # noqa: TC001
from backend.application.dto.candidate_dtos import (  # noqa: TC001
    DecidePhraseRequest,
    ReplaceWithExampleRequest,
    SetPhraseBoundaryRequest,
)
from backend.application.dto.cloze_dtos import SaveClozeRequest  # noqa: TC001
from backend.application.dto.follow_up_dtos import FollowUpRequest  # noqa: TC001
from backend.application.dto.source_dtos import StoredCandidateDTO  # noqa: TC001
from backend.domain.exceptions import (
    AIServiceError,
    AlreadyInAnkiError,
    CardDecisionLockedError,
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    DecidedElsewhereError,
    InvalidClozeError,
    InvalidPhraseError,
    PhraseChangedError,
    PhraseNotFoundError,
    PhrasePolishNotSupportedError,
    SourceHasNoDocumentError,
    SourceOperationBusyError,
)
from backend.domain.services.card_decision import DecisionAction
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/phrases", tags=["phrases"])

REFUSED_DECISIONS = (
    AlreadyInAnkiError, CardDecisionLockedError, DecidedElsewhereError, ClozeNotAllowedError,
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
) -> StoredCandidateDTO:
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
) -> StoredCandidateDTO:
    try:
        result = container.replace_with_example_use_case(session).execute(
            phrase_id, request.example_text,
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AlreadyInAnkiError as e:
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
