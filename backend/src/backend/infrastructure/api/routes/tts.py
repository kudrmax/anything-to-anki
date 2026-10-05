from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.exceptions import CandidateNotFoundError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["tts"])


@router.post("/candidates/{candidate_id}/generate-tts", status_code=202)
def enqueue_candidate_tts(
    candidate_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    """Enqueue TTS generation for a single candidate (any source type)."""
    try:
        container.enqueue_candidate_tts_use_case(session).execute(candidate_id)
    except CandidateNotFoundError as e:
        raise HTTPException(status_code=404, detail="Candidate not found") from e
    session.commit()
    return {"status": "enqueued"}
