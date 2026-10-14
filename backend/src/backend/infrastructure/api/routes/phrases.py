"""Actions on a card: a phrase of a word."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.candidate_dtos import (  # noqa: TC001
    DecidePhraseRequest,
    ReplaceWithExampleRequest,
    SetPhraseBoundaryRequest,
)
from backend.application.dto.cloze_dtos import SaveClozeRequest  # noqa: TC001
from backend.application.dto.source_dtos import StoredCandidateDTO  # noqa: TC001
from backend.domain.exceptions import (
    AlreadyInAnkiError,
    CardDecisionLockedError,
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    DecidedElsewhereError,
    InvalidClozeError,
    InvalidPhraseError,
    PhraseNotFoundError,
    SourceHasNoDocumentError,
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
