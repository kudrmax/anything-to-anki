from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.known_word_dtos import KnownWordDTO  # noqa: TC001
from backend.domain.exceptions import KnownWordNotFoundError, SourceOperationBusyError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/known-words", tags=["known-words"])


@router.get("")
def list_known_words(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[KnownWordDTO]:
    use_case = container.manage_known_words_use_case(session)
    return use_case.list_all()


@router.delete("/{removal_key:path}")
def delete_known_word(
    removal_key: str,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    """Removes an entry of the Known list by the key the list gave it. Removing a word's
    last entry, or a word Known by its timer, makes its cards new in every source."""
    try:
        container.manage_known_words_use_case(session).remove(removal_key)
    except KnownWordNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    session.commit()
    return {"deleted": removal_key}
