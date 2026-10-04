from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.generation_dtos import GenerationStatusDTO  # noqa: TC001
from backend.domain.exceptions import (
    GenerationAlreadyRunningError,
    GenerationBlockedError,
    GenerationNotSupportedError,
    SourceNotFoundError,
    SourceNotTopicError,
    TopicTargetsAlreadyGeneratedError,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.generation_kind import (
    GenerationKind,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.domain.value_objects.generation_scope import (
    GenerationScope,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


@router.post("/sources/{source_id}/topic-targets/generate", status_code=202)
def enqueue_topic_generation(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    """Enqueue the AI step of a topic source: turning its request into targets."""
    try:
        container.enqueue_topic_generation_use_case(session).execute(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceNotTopicError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (TopicTargetsAlreadyGeneratedError, GenerationAlreadyRunningError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"status": "queued"}


@router.get("/sources/{source_id}/generation")
def get_generation_status(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GenerationStatusDTO:
    """How far every kind of background generation got for the source's cards."""
    try:
        return container.get_generation_status_use_case(session).execute(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/sources/{source_id}/generation/{kind}", status_code=202)
def run_generation(
    source_id: int,
    kind: GenerationKind,
    scope: GenerationScope,
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Queue one kind of generation for the cards in `scope`, in the `sort` order."""
    try:
        enqueued = container.run_generation_use_case(session).execute(
            source_id, kind, scope, sort_order=sort,
        )
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except GenerationNotSupportedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except GenerationBlockedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"enqueued": enqueued}


@router.post("/sources/{source_id}/generation/{kind}/cancel")
def cancel_generation(
    source_id: int,
    kind: GenerationKind,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued AND running jobs of one kind of generation."""
    cancelled = container.cancel_generation_use_case(session).execute(source_id, kind)
    session.commit()
    return {"cancelled": cancelled}
