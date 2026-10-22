from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.level_change_dtos import LevelChangeStatusDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container

if TYPE_CHECKING:
    from backend.infrastructure.container import Container

router = APIRouter(prefix="/api/level-change", tags=["level-change"])


@router.get("")
def get_level_change(
    container: Container = Depends(get_container),  # noqa: B008
) -> LevelChangeStatusDTO:
    return container.level_change_progress().status()


@router.post("/cancel", status_code=202)
def cancel_level_change(
    container: Container = Depends(get_container),  # noqa: B008
) -> LevelChangeStatusDTO:
    progress = container.level_change_progress()
    if not progress.cancel():
        raise HTTPException(status_code=409, detail="Nothing to cancel")
    return progress.status()
