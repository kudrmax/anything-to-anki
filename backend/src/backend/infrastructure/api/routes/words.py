from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.application.dto.review_dtos import (  # noqa: TC001 — FastAPI's at runtime
    ReviewContext,
    ReviewUpdateDTO,
)
from backend.application.dto.target_image_dtos import (  # noqa: TC001
    ApplyTargetImageRequest,
    TargetImageOptionsDTO,
    TargetImageSuggestionsDTO,
)
from backend.domain.exceptions import (
    CandidateNotFoundError,
    ImageSearchError,
    UnknownImageUrlError,
)
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.api.review_context import review_context, review_expired
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
    from backend.application.use_cases.paste_target_image import PasteTargetImageUseCase
    from backend.application.use_cases.review_mutation import ReviewMutation
    from backend.application.use_cases.search_target_images import SearchTargetImagesUseCase
    from backend.application.use_cases.suggest_target_images import SuggestTargetImagesUseCase

# Actions on a word of a source; its cards (phrases) have theirs under /phrases.
router = APIRouter(prefix="/words", tags=["words"])


@router.get("/{candidate_id}/image-options")
def search_target_images(
    candidate_id: int,
    query: str | None = None,
    search: SearchTargetImagesUseCase = Depends(  # noqa: B008
        use_case(Container.search_target_images_use_case),  # noqa: B008
    ),
) -> TargetImageOptionsDTO:
    try:
        return search.execute(candidate_id, query)
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ImageSearchError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/{candidate_id}/image-suggestions")
def suggest_target_images(
    candidate_id: int,
    suggest: SuggestTargetImagesUseCase = Depends(  # noqa: B008
        use_case(Container.suggest_target_images_use_case),  # noqa: B008
    ),
) -> TargetImageSuggestionsDTO:
    try:
        return suggest.execute(candidate_id)
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{candidate_id}/image")
def apply_target_image(
    candidate_id: int,
    request: ApplyTargetImageRequest,
    apply: ApplyTargetImageUseCase = Depends(  # noqa: B008
        use_case(Container.apply_target_image_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    try:
        with review_expired():
            _, update = mutation.edit(ctx, lambda: apply.execute(candidate_id, request.url))
        return update
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except UnknownImageUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=502, detail=f"Failed to download the picture: {e}") from e


@router.put("/{candidate_id}/image/pasted")
async def paste_target_image(
    candidate_id: int,
    request: Request,
    paste: PasteTargetImageUseCase = Depends(  # noqa: B008
        use_case(Container.paste_target_image_use_case),  # noqa: B008
    ),
    ctx: ReviewContext = Depends(review_context),  # noqa: B008
    mutation: ReviewMutation = Depends(use_case(Container.review_mutation)),  # noqa: B008
) -> ReviewUpdateDTO:
    picture = await request.body()
    try:
        with review_expired():
            _, update = await asyncio.to_thread(
                mutation.edit, ctx, lambda: paste.execute(candidate_id, picture),
            )
        return update
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"Not a picture: {e}") from e
