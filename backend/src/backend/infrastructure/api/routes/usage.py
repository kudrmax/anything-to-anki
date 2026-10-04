from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.ai_usage_dtos import (
    AIUsageStatsDTO,  # noqa: TC001 — FastAPI reads the response model at runtime
    UsagePeriod,
)
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/api/usage", tags=["usage"])

DEFAULT_TIMEZONE = "UTC"


@router.get("")
def get_ai_usage(
    period: UsagePeriod = UsagePeriod.MONTH,
    tz: str = DEFAULT_TIMEZONE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> AIUsageStatsDTO:
    use_case = container.get_ai_usage_stats_use_case(session)
    try:
        return use_case.execute(period, tz)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
