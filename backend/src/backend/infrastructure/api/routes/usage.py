from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.ai_usage_dtos import (
    AIUsageStatsDTO,  # noqa: TC001 — FastAPI reads the response model at runtime
    UsagePeriod,
)
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.get_ai_usage_stats import GetAIUsageStatsUseCase

router = APIRouter(prefix="/api/usage", tags=["usage"])

DEFAULT_TIMEZONE = "UTC"


@router.get("")
def get_ai_usage(
    period: UsagePeriod = UsagePeriod.MONTH,
    tz: str = DEFAULT_TIMEZONE,
    usage: GetAIUsageStatsUseCase = Depends(  # noqa: B008
        use_case(Container.get_ai_usage_stats_use_case),  # noqa: B008
    ),
) -> AIUsageStatsDTO:
    try:
        return usage.execute(period, tz)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
