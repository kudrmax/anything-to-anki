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
    ActionRefusedError,
    AIServiceError,
    AIUnavailableError,
    CandidateNotPolishedError,
    ClozeNotAllowedError,
    ClozePhraseChangedError,
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
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
    from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
    from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
    from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
    from backend.application.use_cases.preview_cloze import PreviewClozeUseCase
    from backend.application.use_cases.regenerate_phrase_media import RegeneratePhraseMediaUseCase
    from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
    from backend.application.use_cases.report_candidate import ReportCandidateUseCase
    from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
    from backend.application.use_cases.save_cloze import SaveClozeUseCase
    from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase

router = APIRouter(prefix="/phrases", tags=["phrases"])

# The press table refuses the button, or a Rebuild or a refresh holds the source: no card
# changes by hand meanwhile.
REFUSED_DECISIONS = (ActionRefusedError, SourceOperationBusyError)
# The source is busy with a long operation, or one changed the phrase meanwhile.
REFUSED_GENERATION = (SourceOperationBusyError, PhraseChangedError)


@router.post("/{phrase_id}/decision")
def decide_phrase(
    phrase_id: int,
    request: DecidePhraseRequest,
    decide: DecidePhraseUseCase = Depends(  # noqa: B008
        use_case(Container.decide_phrase_use_case),  # noqa: B008
    ),
) -> CardDTO:
    """A press of a decision button; the answer is the card after it."""
    try:
        card = decide.decide(phrase_id, request.button)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_DECISIONS as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return card


@router.put("/{phrase_id}/cloze")
def save_cloze(
    phrase_id: int,
    request: SaveClozeRequest,
    save: SaveClozeUseCase = Depends(use_case(Container.save_cloze_use_case)),  # noqa: B008
) -> CardDTO:
    try:
        candidate = save.execute(
            phrase_id,
            request.phrase,
            request.hidden_word_indices,
            ClozeHintKind(request.hint_kind),
            request.custom_hint,
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (*REFUSED_DECISIONS, ClozeNotAllowedError, ClozePhraseChangedError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidClozeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return candidate


@router.post("/{phrase_id}/cloze/preview")
def preview_cloze(
    phrase_id: int,
    request: PreviewClozeRequest,
    preview: PreviewClozeUseCase = Depends(  # noqa: B008
        use_case(Container.preview_cloze_use_case),  # noqa: B008
    ),
) -> ClozePreviewDTO:
    try:
        return preview.execute(phrase_id, request)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidClozeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/{phrase_id}/report", status_code=201)
def report_phrase(
    phrase_id: int,
    request: ReportCandidateRequest,
    report_card: ReportCandidateUseCase = Depends(  # noqa: B008
        use_case(Container.report_candidate_use_case),  # noqa: B008
    ),
) -> CardReportDTO:
    try:
        report = report_card.execute(phrase_id, request)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (EmptyReportCommentError, UnknownReportReasonError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return report


@router.put("/{phrase_id}/polish/reverted")
def revert_phrase_polish(
    phrase_id: int,
    request: RevertPolishRequest,
    revert: RevertPhrasePolishUseCase = Depends(  # noqa: B008
        use_case(Container.revert_phrase_polish_use_case),  # noqa: B008
    ),
) -> dict[str, Any]:
    try:
        revert.execute(phrase_id, request.reverted)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (CandidateNotPolishedError, SourceOperationBusyError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"id": phrase_id, "reverted": request.reverted}


@router.put("/{phrase_id}/phrase")
def edit_phrase(
    phrase_id: int,
    request: EditPhraseRequest,
    edit: EditCardPhraseUseCase = Depends(  # noqa: B008
        use_case(Container.edit_card_phrase_use_case),  # noqa: B008
    ),
) -> dict[str, Any]:
    """The text of the card's phrase, rewritten by hand."""
    try:
        edit.execute(phrase_id, request.phrase)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"id": phrase_id}


@router.put("/{phrase_id}/phrase-boundary")
def set_phrase_boundary(
    phrase_id: int,
    request: SetPhraseBoundaryRequest,
    select: SetPhraseBoundaryUseCase = Depends(  # noqa: B008
        use_case(Container.set_phrase_boundary_use_case),  # noqa: B008
    ),
) -> dict[str, Any]:
    """The phrase of a card, selected anew on the source screen."""
    try:
        phrase = select.execute(
            phrase_id, request.selection,
        )
    except (PhraseNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"id": phrase_id, "context_fragment": phrase}


@router.post("/{phrase_id}/replace-with-example", status_code=201)
def replace_with_example(
    phrase_id: int,
    request: ReplaceWithExampleRequest,
    replace: ReplaceWithExampleUseCase = Depends(  # noqa: B008
        use_case(Container.replace_with_example_use_case),  # noqa: B008
    ),
) -> CardDTO:
    try:
        result = replace.execute(
            phrase_id, request.example_text,
        )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.post("/{phrase_id}/polish", status_code=202)
def polish_phrase_again(
    phrase_id: int,
    polish: EnqueuePhrasePolishUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_phrase_polish_use_case),  # noqa: B008
    ),
) -> dict[str, str]:
    try:
        polish.execute(phrase_id)
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
    tts: EnqueuePhraseTTSUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_phrase_tts_use_case),  # noqa: B008
    ),
) -> dict[str, str]:
    """Enqueue TTS generation for one phrase (any source type)."""
    try:
        tts.execute(phrase_id)
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"status": "enqueued"}


@router.post("/{phrase_id}/regenerate-media", status_code=202)
def regenerate_phrase_media(
    phrase_id: int,
    regenerate: RegeneratePhraseMediaUseCase = Depends(  # noqa: B008
        use_case(Container.regenerate_phrase_media_use_case),  # noqa: B008
    ),
) -> dict[str, str]:
    try:
        regenerate.execute(phrase_id)
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
    meaning: GenerateMeaningUseCase = Depends(  # noqa: B008
        use_case(Container.generate_meaning_use_case),  # noqa: B008
    ),
) -> GenerateMeaningResponseDTO:
    try:
        if follow_up is not None:
            result = await asyncio.to_thread(
                meaning.execute_follow_up, phrase_id, follow_up.action, follow_up.text,
            )
        else:
            result = await asyncio.to_thread(meaning.execute, phrase_id)
        return result
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except AIUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except AIServiceError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
