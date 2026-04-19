from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import (  # noqa: TC001
    AnkiStatusDTO,
    AnkiTemplatesDTO,
    CardPreviewDTO,
    CreateNoteTypeRequest,
    CreateNoteTypeResponseDTO,
    SyncResultDTO,
    VerifyNoteTypeRequest,
    VerifyNoteTypeResponseDTO,
)
from backend.application.use_cases.manage_settings import build_anki_field_map
from backend.domain.exceptions import AnkiNotAvailableError, AnkiSyncError
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


@router.get("/sources/{source_id}/cards")
def get_source_cards(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[CardPreviewDTO]:
    use_case = container.get_source_cards_use_case(session)
    return use_case.execute(source_id)


@router.post("/sources/{source_id}/sync-to-anki")
def sync_to_anki(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SyncResultDTO:
    use_case = container.sync_to_anki_use_case(session)
    try:
        result = use_case.execute(source_id)
        session.commit()
        return result
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnkiSyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/anki/templates")
def get_anki_templates(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AnkiTemplatesDTO:
    settings_uc = container.manage_settings_use_case(session)
    settings = settings_uc.get_settings()
    field_map = build_anki_field_map({
        "anki_field_sentence": settings.anki_field_sentence,
        "anki_field_target_word": settings.anki_field_target_word,
        "anki_field_meaning": settings.anki_field_meaning,
        "anki_field_ipa": settings.anki_field_ipa,
        "anki_field_image": settings.anki_field_image,
        "anki_field_audio": settings.anki_field_audio,
        "anki_field_translation": settings.anki_field_translation,
        "anki_field_synonyms": settings.anki_field_synonyms,
        "anki_field_examples": settings.anki_field_examples,
    })
    renderer = container.anki_template_renderer()
    templates = renderer.render_all(field_map)
    return AnkiTemplatesDTO(**templates)
