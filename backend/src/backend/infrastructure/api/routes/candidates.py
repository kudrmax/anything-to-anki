from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.ai_dtos import GenerateMeaningResponseDTO  # noqa: TC001
from backend.application.dto.candidate_dtos import MarkCandidateRequest, UpdateContextFragmentRequest  # noqa: TC001
from backend.domain.exceptions import AIServiceError, CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.patch("/{candidate_id}")
def mark_candidate(
    candidate_id: int,
    request: MarkCandidateRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        use_case = container.mark_candidate_use_case(session)
        status = CandidateStatus(request.status)
        use_case.execute(candidate_id, status)
        session.commit()
        return {"id": candidate_id, "status": request.status}
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{candidate_id}/context-fragment")
def update_context_fragment(
    candidate_id: int,
    request: UpdateContextFragmentRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
    repo = SqlaCandidateRepository(session)
    candidate = repo.get_by_id(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")
    repo.update_context_fragment(candidate_id, request.context_fragment)
    session.commit()
    return {"id": candidate_id, "context_fragment": request.context_fragment}


@router.post("/{candidate_id}/generate-meaning")
async def generate_meaning(
    candidate_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GenerateMeaningResponseDTO:
    try:
        use_case = container.generate_meaning_use_case(session)
        result = await asyncio.to_thread(use_case.execute, candidate_id)
        session.commit()
        return result
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AIServiceError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
