from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import (  # noqa: TC001
    AnkiStatusDTO,
    AnkiTemplatesDTO,
    CreateNoteTypeRequest,
    CreateNoteTypeResponseDTO,
    VerifyNoteTypeRequest,
    VerifyNoteTypeResponseDTO,
)
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
def verify_note_type(
    request: VerifyNoteTypeRequest,
    container: Container = Depends(get_container),  # noqa: B008
) -> VerifyNoteTypeResponseDTO:
    connector = container.anki_connector()
    if not connector.is_available():
        raise HTTPException(status_code=503, detail="Anki is not available")
    available_fields = connector.get_model_field_names(request.note_type)
    if available_fields is None:
        return VerifyNoteTypeResponseDTO(
            valid=False,
            available_fields=[],
            missing_fields=request.required_fields,
        )
    missing = [f for f in request.required_fields if f and f not in available_fields]
    return VerifyNoteTypeResponseDTO(
        valid=len(missing) == 0,
        available_fields=available_fields,
        missing_fields=missing,
    )


@router.post("/anki/create-note-type")
def create_note_type(
    request: CreateNoteTypeRequest,
    container: Container = Depends(get_container),  # noqa: B008
) -> CreateNoteTypeResponseDTO:
    connector = container.anki_connector()
    if not connector.is_available():
        raise HTTPException(status_code=503, detail="Anki is not available")
    fields = [f for f in request.fields if f]
    if not fields:
        raise HTTPException(status_code=422, detail="At least one field is required")
    already_existed = connector.get_model_field_names(request.note_type) is not None
    connector.ensure_note_type(request.note_type, fields)
    return CreateNoteTypeResponseDTO(already_existed=already_existed)


@router.get("/anki/templates")
def get_anki_templates(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiTemplatesDTO:
    return container.get_anki_templates_use_case(session).execute()
