from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from backend.application.dto.known_word_dtos import KnownWordDTO  # noqa: TC001
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


@router.delete("/{known_word_id}")
def delete_known_word(
    known_word_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.manage_known_words_use_case(session)
    use_case.delete(known_word_id)
    session.commit()
    return {"deleted": known_word_id}
