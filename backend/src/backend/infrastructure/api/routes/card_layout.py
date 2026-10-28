from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.card_layout_dtos import (  # noqa: TC001
    CardLayoutEdit,
    CardLayoutViewDTO,
)
from backend.domain.exceptions import CardLayoutEditError
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.manage_card_layout import ManageCardLayoutUseCase

router = APIRouter(prefix="/api/card-layout", tags=["card-layout"])


@router.get("")
def get_card_layout(
    layouts: ManageCardLayoutUseCase = Depends(  # noqa: B008
        use_case(Container.manage_card_layout_use_case),  # noqa: B008
    ),
) -> CardLayoutViewDTO:
    return layouts.get()


@router.post("/edits")
def edit_card_layout(
    edit: CardLayoutEdit,
    layouts: ManageCardLayoutUseCase = Depends(  # noqa: B008
        use_case(Container.manage_card_layout_use_case),  # noqa: B008
    ),
) -> CardLayoutViewDTO:
    try:
        return layouts.edit(edit)
    except CardLayoutEditError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
