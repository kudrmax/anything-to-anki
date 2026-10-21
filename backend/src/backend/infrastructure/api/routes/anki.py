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
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
    from backend.application.use_cases.get_anki_templates import GetAnkiTemplatesUseCase
    from backend.application.use_cases.manage_anki_note_types import ManageAnkiNoteTypesUseCase

router = APIRouter(tags=["anki"])


@router.get("/anki/status")
def get_anki_status(
    status: GetAnkiStatusUseCase = Depends(  # noqa: B008
        use_case(Container.get_anki_status_use_case),  # noqa: B008
    ),
) -> AnkiStatusDTO:
    return status.execute()


@router.get("/anki/note-types")
def check_note_types(
    note_types: ManageAnkiNoteTypesUseCase = Depends(  # noqa: B008
        use_case(Container.manage_anki_note_types_use_case),  # noqa: B008
    ),
) -> list[NoteTypeCheckDTO]:
    try:
        return note_types.check()
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.post("/anki/note-types/{kind}/fix")
def fix_note_type(
    kind: NoteTypeKind,
    note_types: ManageAnkiNoteTypesUseCase = Depends(  # noqa: B008
        use_case(Container.manage_anki_note_types_use_case),  # noqa: B008
    ),
) -> NoteTypeCheckDTO:
    try:
        return note_types.fix(kind)
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail="Anki is not available") from exc


@router.get("/anki/templates")
def get_anki_templates(
    templates: GetAnkiTemplatesUseCase = Depends(  # noqa: B008
        use_case(Container.get_anki_templates_use_case),  # noqa: B008
    ),
) -> AnkiTemplatesDTO:
    return templates.execute()


