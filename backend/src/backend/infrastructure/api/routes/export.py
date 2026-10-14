from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import GlobalExportDTO, SyncResultDTO  # noqa: TC001
from backend.domain.exceptions import (
    AnkiNotAvailableError,
    AnkiNoteTypeIncompleteError,
    AnkiSyncError,
    CollectionNotFoundError,
)
from backend.domain.value_objects.export_group import ExportGroup  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session
from backend.infrastructure.api.scope_param import parse_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(tags=["export"])


@router.get("/export/cards")
def get_scope_export_cards(
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GlobalExportDTO:
    use_case = container.get_export_cards_use_case(session)
    try:
        return use_case.execute_scope(parse_scope(scope))
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/export/cards/{source_id}")
def get_source_export_cards(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GlobalExportDTO:
    use_case = container.get_export_cards_use_case(session)
    return use_case.execute(source_id)


@router.post("/export/sync-to-anki")
def sync_scope_to_anki(
    group: ExportGroup,
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SyncResultDTO:
    parsed_scope = parse_scope(scope)
    use_case = container.sync_to_anki_use_case(session)
    try:
        result = use_case.execute_scope(parsed_scope, group)
        session.commit()
        return result
    except CollectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnkiNoteTypeIncompleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AnkiSyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/export/sync-to-anki/{source_id}")
def sync_source_to_anki(
    source_id: int,
    group: ExportGroup,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SyncResultDTO:
    use_case = container.sync_to_anki_use_case(session)
    try:
        result = use_case.execute(source_id, group)
        session.commit()
        return result
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnkiNoteTypeIncompleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AnkiSyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
