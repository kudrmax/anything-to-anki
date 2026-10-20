from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.anki_dtos import LearningWordsDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.get_learning_words import GetLearningWordsUseCase

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/learning")
def list_learning_words(
    learning: GetLearningWordsUseCase = Depends(  # noqa: B008
        use_case(Container.get_learning_words_use_case),  # noqa: B008
    ),
) -> LearningWordsDTO:
    """The words the user is learning, read-only."""
    return learning.execute()
