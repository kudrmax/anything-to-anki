from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.application.dto.target_image_dtos import (  # noqa: TC001
    ApplyTargetImageRequest,
    TargetImageOptionsDTO,
)
from backend.domain.exceptions import (
    CandidateNotFoundError,
    ImageSearchError,
    UnknownImageUrlError,
)
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

# Actions on a word of a source; its cards (phrases) have theirs under /phrases.
router = APIRouter(prefix="/words", tags=["words"])


@router.get("/{candidate_id}/image-options")
def search_target_images(
    candidate_id: int,
    query: str | None = None,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> TargetImageOptionsDTO:
    try:
        return container.search_target_images_use_case(session).execute(candidate_id, query)
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ImageSearchError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.put("/{candidate_id}/image")
def apply_target_image(
    candidate_id: int,
    request: ApplyTargetImageRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    try:
        container.apply_target_image_use_case(session).execute(candidate_id, request.url)
        session.commit()
        return {"status": "applied"}
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
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    picture = await request.body()
    try:
        use_case = container.paste_target_image_use_case(session)
        await asyncio.to_thread(use_case.execute, candidate_id, picture)
        session.commit()
        return {"status": "applied"}
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(status_code=400, detail=f"Not a picture: {e}") from e
