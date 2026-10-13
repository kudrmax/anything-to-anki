from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from backend.application.dto.unknown_word_dtos import UnknownWordDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/unknown-words", tags=["unknown-words"])


@router.get("")
def list_unknown_words(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[UnknownWordDTO]:
    use_case = container.manage_unknown_words_use_case(session)
    return use_case.list_all()


@router.delete("/{unknown_word_id}")
def delete_unknown_word(
    unknown_word_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    use_case = container.manage_unknown_words_use_case(session)
    use_case.delete(unknown_word_id)
    session.commit()
    return {"deleted": unknown_word_id}
