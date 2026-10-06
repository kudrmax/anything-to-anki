from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import (  # noqa: TC001
    AnkiStatusDTO,
    AnkiTemplatesDTO,
    NoteTypeCheckDTO,
)
from backend.application.utils.anki_note_types import NoteTypeKind  # noqa: TC001
from backend.domain.exceptions import AnkiNotAvailableError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["anki"])


@router.get("/anki/status")
def get_anki_status(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiStatusDTO:
    use_case = container.get_anki_status_use_case(session)
    return use_case.execute()


@router.get("/anki/note-types")
def check_note_types(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[NoteTypeCheckDTO]:
    try:
        return container.manage_anki_note_types_use_case(session).check()
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.post("/anki/note-types/{kind}/fix")
def fix_note_type(
    kind: NoteTypeKind,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> NoteTypeCheckDTO:
    try:
        return container.manage_anki_note_types_use_case(session).fix(kind)
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.get("/anki/templates")
def get_anki_templates(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiTemplatesDTO:
    return container.get_anki_templates_use_case(session).execute()
