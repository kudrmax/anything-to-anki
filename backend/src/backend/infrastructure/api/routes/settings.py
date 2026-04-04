from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.settings_dtos import SettingsDTO, UpdateSettingsRequest  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SettingsDTO:
    use_case = container.manage_settings_use_case(session)
    return use_case.get_settings()


@router.patch("")
def update_settings(
    request: UpdateSettingsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SettingsDTO:
    use_case = container.manage_settings_use_case(session)
    use_case.update_cefr_level(request.cefr_level)
    session.commit()
    return use_case.get_settings()
