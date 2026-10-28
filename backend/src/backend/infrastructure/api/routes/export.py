from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.anki_dtos import GlobalExportDTO, SyncResultDTO  # noqa: TC001
from backend.domain.exceptions import (
    AnkiNotAvailableError,
    AnkiNoteTypeIncompleteError,
    AnkiSyncError,
    CollectionNotFoundError,
    SourceNotFoundError,
)
from backend.domain.value_objects.export_group import ExportGroup  # noqa: TC001
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.api.scope_param import parse_scope
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.fill_incomplete_cards import FillIncompleteCardsUseCase
    from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
    from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase

router = APIRouter(tags=["export"])


@router.get("/export/cards")
def get_scope_export_cards(
    scope: str = "all",
    export_cards: GetExportCardsUseCase = Depends(  # noqa: B008
        use_case(Container.get_export_cards_use_case),  # noqa: B008
    ),
) -> GlobalExportDTO:
    try:
        return export_cards.execute(parse_scope(scope))
    except (CollectionNotFoundError, SourceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/export/fill-missing")
def fill_scope_missing(
    scope: str = "all",
    fill: FillIncompleteCardsUseCase = Depends(  # noqa: B008
        use_case(Container.fill_incomplete_cards_use_case),  # noqa: B008
    ),
    export_cards: GetExportCardsUseCase = Depends(  # noqa: B008
        use_case(Container.get_export_cards_use_case),  # noqa: B008
    ),
) -> GlobalExportDTO:
    """Queue what the set's incomplete cards lack; the export as it stands after."""
    parsed_scope = parse_scope(scope)
    try:
        fill.execute(parsed_scope)
        return export_cards.execute(parsed_scope)
    except (CollectionNotFoundError, SourceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/export/sync-to-anki")
def sync_scope_to_anki(
    group: ExportGroup,
    scope: str = "all",
    sync: SyncToAnkiUseCase = Depends(use_case(Container.sync_to_anki_use_case)),  # noqa: B008
) -> SyncResultDTO:
    parsed_scope = parse_scope(scope)
    try:
        result = sync.execute(parsed_scope, group)
        return result
    except (CollectionNotFoundError, SourceNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AnkiNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AnkiNoteTypeIncompleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AnkiSyncError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
