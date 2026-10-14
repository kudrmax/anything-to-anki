from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.anki_dtos import LearningWordsDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/learning")
def list_learning_words(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> LearningWordsDTO:
    """The words the user is learning, read-only."""
    return container.get_learning_words_use_case(session).execute()
