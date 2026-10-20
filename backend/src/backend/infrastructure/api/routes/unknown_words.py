from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from backend.application.dto.unknown_word_dtos import UnknownWordDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.manage_unknown_words import ManageUnknownWordsUseCase

router = APIRouter(prefix="/unknown-words", tags=["unknown-words"])


@router.get("")
def list_unknown_words(
    unknown_words: ManageUnknownWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_unknown_words_use_case),  # noqa: B008
    ),
) -> list[UnknownWordDTO]:
    return unknown_words.list_all()


@router.delete("/{unknown_word_id}")
def delete_unknown_word(
    unknown_word_id: int,
    unknown_words: ManageUnknownWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_unknown_words_use_case),  # noqa: B008
    ),
) -> dict[str, Any]:
    unknown_words.delete(unknown_word_id)
    return {"deleted": unknown_word_id}
