"""Actions on a card: a phrase of a word."""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.candidate_dtos import (  # noqa: TC001
    DecidePhraseRequest,
    EditPhraseRequest,
    ReplaceWithExampleRequest,
    RevertPolishRequest,
    SetPhraseBoundaryRequest,
)
from backend.application.dto.card_report_dtos import (  # noqa: TC001
    ReportCandidateRequest,
)
from backend.application.dto.cloze_dtos import (  # noqa: TC001
    ClozePreviewDTO,
    PreviewClozeRequest,
    SaveClozeRequest,
)
from backend.application.dto.follow_up_dtos import FollowUpRequest  # noqa: TC001
from backend.application.dto.review_dtos import (  # noqa: TC001 — FastAPI's at runtime
    ReviewContext,
    ReviewUpdateDTO,
)
from backend.domain.exceptions import (
    ActionRefusedError,
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
from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.api.review_context import review_context, review_expired
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
    from backend.application.use_cases.enqueue_phrase_meaning import EnqueuePhraseMeaningUseCase
    from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
    from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
    from backend.application.use_cases.preview_cloze import PreviewClozeUseCase
    from backend.application.use_cases.regenerate_phrase_media import RegeneratePhraseMediaUseCase
    from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
    from backend.application.use_cases.replace_with_target import ReplaceWithTargetUseCase
    from backend.application.use_cases.report_candidate import ReportCandidateUseCase
    from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
    from backend.application.use_cases.review_mutation import ReviewMutation
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
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """A press of a decision button; the answer is what changed, with the next focus."""
    try:
        with review_expired():
            return mutation.press(
                ctx, phrase_id, lambda: decide.decide(phrase_id, request.button),
            )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_DECISIONS as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{phrase_id}/decision/undo")
def undo_decision(
    phrase_id: int,
    request: DecidePhraseRequest,
    decide: DecidePhraseUseCase = Depends(  # noqa: B008
        use_case(Container.decide_phrase_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The press a decision's answer offered to undo it; the focus goes back to the card."""
    try:
        with review_expired():
            return mutation.undo(
                ctx, phrase_id, lambda: decide.decide(phrase_id, request.button),
            )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_DECISIONS as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.put("/{phrase_id}/cloze")
def save_cloze(
    phrase_id: int,
    request: SaveClozeRequest,
    save: SaveClozeUseCase = Depends(use_case(Container.save_cloze_use_case)),  # noqa: B008
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The cloze saved, which decides the card; the answer is what changed, with the next
    focus."""
    try:
        with review_expired():
            return mutation.press(ctx, phrase_id, lambda: save.execute(
                phrase_id,
                request.phrase,
                request.hidden_word_indices,
                ClozeHintKind(request.hint_kind),
                request.custom_hint,
            ))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (*REFUSED_DECISIONS, ClozeNotAllowedError, ClozePhraseChangedError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidClozeError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: report_card.execute(phrase_id, request))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (EmptyReportCommentError, UnknownReportReasonError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return update


@router.put("/{phrase_id}/polish/reverted")
def revert_phrase_polish(
    phrase_id: int,
    request: RevertPolishRequest,
    revert: RevertPhrasePolishUseCase = Depends(  # noqa: B008
        use_case(Container.revert_phrase_polish_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    try:
        with review_expired():
            _, update = mutation.edit(
                ctx, lambda: revert.execute(phrase_id, request.reverted),
            )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (CandidateNotPolishedError, SourceOperationBusyError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return update


@router.put("/{phrase_id}/phrase")
def edit_phrase(
    phrase_id: int,
    request: EditPhraseRequest,
    edit: EditCardPhraseUseCase = Depends(  # noqa: B008
        use_case(Container.edit_card_phrase_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The text of the card's phrase, rewritten by hand."""
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: edit.execute(phrase_id, request.phrase))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return update


@router.put("/{phrase_id}/phrase-boundary")
def set_phrase_boundary(
    phrase_id: int,
    request: SetPhraseBoundaryRequest,
    select: SetPhraseBoundaryUseCase = Depends(  # noqa: B008
        use_case(Container.set_phrase_boundary_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The phrase of a card, selected anew on the source screen."""
    try:
        with review_expired():
            _, update = mutation.edit(
                ctx, lambda: select.execute(phrase_id, request.selection),
            )
    except (PhraseNotFoundError, SourceHasNoDocumentError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return update


@router.post("/{phrase_id}/replace-with-example", status_code=201)
def replace_with_example(
    phrase_id: int,
    request: ReplaceWithExampleRequest,
    replace: ReplaceWithExampleUseCase = Depends(  # noqa: B008
        use_case(Container.replace_with_example_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The card replaced by an example: the new card takes its place and the focus."""
    try:
        with review_expired():
            return mutation.replace(
                ctx, phrase_id, lambda: replace.execute(phrase_id, request.example_text),
            )
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{phrase_id}/replace-with-target", status_code=201)
def replace_with_target(
    phrase_id: int,
    replace: ReplaceWithTargetUseCase = Depends(  # noqa: B008
        use_case(Container.replace_with_target_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """The card replaced by its bare target: the new card takes its place and the focus."""
    try:
        with review_expired():
            return mutation.replace(ctx, phrase_id, lambda: replace.execute(phrase_id))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except InvalidPhraseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/{phrase_id}/polish", status_code=202)
def polish_phrase_again(
    phrase_id: int,
    polish: EnqueuePhrasePolishUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_phrase_polish_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: polish.execute(phrase_id))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PhrasePolishNotSupportedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return update


@router.post("/{phrase_id}/generate-tts", status_code=202)
def enqueue_phrase_tts(
    phrase_id: int,
    tts: EnqueuePhraseTTSUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_phrase_tts_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Enqueue TTS generation for one phrase (any source type)."""
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: tts.execute(phrase_id))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return update


@router.post("/{phrase_id}/regenerate-media", status_code=202)
def regenerate_phrase_media(
    phrase_id: int,
    regenerate: RegeneratePhraseMediaUseCase = Depends(  # noqa: B008
        use_case(Container.regenerate_phrase_media_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: regenerate.execute(phrase_id))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return update


@router.post("/{phrase_id}/generate-meaning", status_code=202)
def generate_meaning(
    phrase_id: int,
    follow_up: FollowUpRequest | None = None,
    meaning: EnqueuePhraseMeaningUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_phrase_meaning_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Queue the phrase's meaning, or a follow-up about it; the worker calls the AI. The
    answer is what changed in the open review."""
    question = (
        MeaningFollowUp(follow_up.action, follow_up.text) if follow_up is not None else None
    )
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: meaning.execute(phrase_id, question))
    except PhraseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except REFUSED_GENERATION as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return update
