from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import (  # noqa: TC001
    AnkiStatusDTO,
    AnkiTemplatesDTO,
    CreateNoteTypesResponseDTO,
    VerifyNoteTypesResponseDTO,
)
from backend.domain.exceptions import AnkiNotAvailableError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["anki"])


@router.get("/anki/status")
def get_anki_status(
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiStatusDTO:
    use_case = container.get_anki_status_use_case()
    return use_case.execute()


@router.post("/anki/verify-note-type")
def verify_note_types(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> VerifyNoteTypesResponseDTO:
    try:
        return container.manage_anki_note_types_use_case(session).verify()
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.post("/anki/create-note-type")
def create_note_types(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CreateNoteTypesResponseDTO:
    try:
        return container.manage_anki_note_types_use_case(session).create()
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.get("/anki/templates")
def get_anki_templates(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiTemplatesDTO:
    return container.get_anki_templates_use_case(session).execute()
