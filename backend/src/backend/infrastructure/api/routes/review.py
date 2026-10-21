from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.dto.document_dtos import (
    ReviewContentsDTO,  # noqa: TC001 — FastAPI serialises it at runtime
)
from backend.application.dto.generation_dtos import GenerationStatusDTO  # noqa: TC001
from backend.application.dto.review_dtos import (
    OpenReviewRequest,  # noqa: TC001 — FastAPI parses it at runtime
    ReviewContext,  # noqa: TC001 — FastAPI injects it at runtime
    ReviewUpdateDTO,  # noqa: TC001 — FastAPI serialises it at runtime
    SectionOpenRequest,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.domain.exceptions import (
    CollectionNotFoundError,
    GenerationBlockedError,
    GenerationNotSupportedError,
    PhraseNotFoundError,
    ReviewNotFoundError,
    ScopeNotReviewableError,
    SourceHasNoDocumentError,
    SourceHasNoUrlError,
    SourceNotFoundError,
    SourceOperationBusyError,
    TextBlockNotFoundError,
    VideoAlreadyDownloadedError,
)
from backend.domain.services.text_chunks import LAST_BLOCK
from backend.domain.value_objects.candidate_section import (
    CandidateSection,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.generation_kind import (
    GenerationKind,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.domain.value_objects.generation_scope import (
    GenerationScope,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.api.review_context import (
    REVIEW_EXPIRED,
    review_context,
    review_expired,
)
from backend.infrastructure.api.scope_param import parse_scope
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from collections.abc import Iterator

    from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
    from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
    from backend.application.use_cases.open_review import OpenReviewUseCase
    from backend.application.use_cases.request_video_download import RequestVideoDownloadUseCase
    from backend.application.use_cases.review_mutation import ReviewMutation
    from backend.application.use_cases.review_window import ReviewWindowUseCase
    from backend.application.use_cases.run_generation import RunGenerationUseCase
    from backend.domain.value_objects.source_scope import SourceScope

# Under /api: /review is the web app's own page, which a reload must get, not this JSON.
router = APIRouter(prefix="/api/review", tags=["review"])


def review_scope(raw: str) -> SourceScope:
    """The set of sources a review request names; a bad token is a 400."""
    return parse_scope(raw)


@contextmanager
def _scope_errors() -> Iterator[None]:
    """A set that is not for review is a 400; a source or collection that is gone, a 404."""
    try:
        yield
    except ScopeNotReviewableError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (SourceNotFoundError, CollectionNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@contextmanager
def _review_errors() -> Iterator[None]:
    """A review no longer held is a 410 the client opens again on; a card it does not
    hold, a source or collection of its set that is gone since, or text it does not have,
    a 404."""
    try:
        yield
    except ReviewNotFoundError as e:
        raise HTTPException(status_code=410, detail=REVIEW_EXPIRED) from e
    except (
        PhraseNotFoundError, SourceNotFoundError, CollectionNotFoundError,
        SourceHasNoDocumentError, TextBlockNotFoundError,
    ) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("")
def open_review(
    request: OpenReviewRequest,
    review: OpenReviewUseCase = Depends(use_case(Container.open_review_use_case)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Opens the review of a set: its order is held under the answer's review id."""
    review_scope(request.scope)
    with _scope_errors(), _review_errors():
        return review.execute(request)


@router.get("/{review_id}/rows")
def review_rows(
    start: int = Query(ge=0),  # noqa: B008
    count: int = Query(ge=1),  # noqa: B008
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewUpdateDTO:
    """`count` rows of the visible list from `start`, at most REVIEW_ROWS_MAX."""
    with _review_errors():
        return window.rows(ctx, start, count)


@router.get("/{review_id}/around/{phrase_id}")
def review_around(
    phrase_id: int,
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewUpdateDTO:
    """The rows around a card, which becomes the current one."""
    with _review_errors():
        return window.around(ctx, phrase_id)


@router.put("/{review_id}/sections/{section}")
def set_review_section(
    section: CandidateSection,
    body: SectionOpenRequest,
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewUpdateDTO:
    """A section opened or folded."""
    with _review_errors():
        return window.set_section(ctx, section, is_open=body.open)


@router.get("/{review_id}/changes")
def review_changes(
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewUpdateDTO:
    """What changed in the open review since the client's revision."""
    with _review_errors():
        return window.changes(ctx)


@router.get("/{review_id}/contents")
def review_contents(
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewContentsDTO:
    """The documents of the set, in the set's order."""
    with _review_errors():
        return window.contents(ctx)


@router.get("/{review_id}/text/{source_id}")
def review_text(
    source_id: int,
    block: int | None = Query(None, ge=LAST_BLOCK),  # noqa: B008
    at: int | None = Query(None, ge=0),  # noqa: B008
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    window: ReviewWindowUseCase = Depends(  # noqa: B008
        use_case(Container.review_window_use_case),  # noqa: B008
    ),
) -> ReviewUpdateDTO:
    """The chunk of the source's text that holds the block (-1 names the last chunk) or
    the character at offset `at` of its text: exactly one of the two."""
    if (block is None) == (at is None):
        raise HTTPException(status_code=422, detail="Give either block or at")
    with _review_errors():
        return window.text(ctx, source_id, block, at)


@router.get("/generation")
def get_generation_status(
    scope: str = "all",
    status: GetGenerationStatusUseCase = Depends(  # noqa: B008
        use_case(Container.get_generation_status_use_case),  # noqa: B008
    ),
) -> GenerationStatusDTO:
    """How far every kind of background generation got for the set's cards."""
    with _scope_errors():
        return status.execute(review_scope(scope))


@router.post("/generation/{kind}", status_code=202)
def run_generation(
    kind: GenerationKind,
    cards: GenerationScope,
    scope: str = "all",
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    run: RunGenerationUseCase = Depends(use_case(Container.run_generation_use_case)),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Queue one kind of generation for the set's `cards`, in the `sort` order. Sources
    that can't run it now are skipped; it fails only when none of them could."""
    set_scope = review_scope(scope)
    with _scope_errors(), review_expired():
        try:
            _, update = mutation.edit(
                ctx, lambda: run.execute(set_scope, kind, cards, sort_order=sort),
            )
        except GenerationNotSupportedError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except (GenerationBlockedError, SourceOperationBusyError) as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    return update


@router.post("/generation/{kind}/cancel")
def cancel_generation(
    kind: GenerationKind,
    scope: str = "all",
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    cancel: CancelGenerationUseCase = Depends(  # noqa: B008
        use_case(Container.cancel_generation_use_case),  # noqa: B008
    ),
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Cancel queued and running jobs of one kind of generation on every source of the set."""
    set_scope = review_scope(scope)
    with _scope_errors(), review_expired():
        _, update = mutation.edit(ctx, lambda: cancel.execute(set_scope, kind))
    return update


@router.post("/download-video", status_code=202)
def download_video(
    scope: str = "all",
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    download: RequestVideoDownloadUseCase = Depends(  # noqa: B008
        use_case(Container.request_video_download_use_case),  # noqa: B008
    ),
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    """Queue the download of every video of the set that isn't here yet."""
    set_scope = review_scope(scope)
    with _scope_errors(), review_expired():
        try:
            _, update = mutation.edit(ctx, lambda: download.execute(set_scope))
        except SourceHasNoUrlError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except VideoAlreadyDownloadedError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    return update
