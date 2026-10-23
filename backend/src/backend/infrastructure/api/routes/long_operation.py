from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.long_operation_dtos import LongOperationStatusDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container

if TYPE_CHECKING:
    from backend.infrastructure.container import Container

router = APIRouter(prefix="/api/long-operation", tags=["long-operation"])


@router.get("")
def get_long_operation(
    container: Container = Depends(get_container),  # noqa: B008
) -> LongOperationStatusDTO:
    return container.long_operation_progress().status()


@router.post("/cancel", status_code=202)
def cancel_long_operation(
    container: Container = Depends(get_container),  # noqa: B008
) -> LongOperationStatusDTO:
    progress = container.long_operation_progress()
    if not progress.cancel():
        raise HTTPException(status_code=409, detail="Nothing to cancel")
    return progress.status()
