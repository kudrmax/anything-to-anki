from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.known_word_dtos import KnownWordDTO  # noqa: TC001
from backend.domain.exceptions import KnownWordNotFoundError, SourceOperationBusyError
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase

router = APIRouter(prefix="/known-words", tags=["known-words"])


@router.get("")
def list_known_words(
    known_words: ManageKnownWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_known_words_use_case),  # noqa: B008
    ),
) -> list[KnownWordDTO]:
    return known_words.list_all()


@router.delete("/{removal_key:path}")
def delete_known_word(
    removal_key: str,
    known_words: ManageKnownWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_known_words_use_case),  # noqa: B008
    ),
) -> dict[str, str]:
    """Removes an entry of the Known list by the key the list gave it. Removing a word's
    last entry, or a word Known by its timer, makes its cards new in every source."""
    try:
        known_words.remove(removal_key)
    except KnownWordNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"deleted": removal_key}
