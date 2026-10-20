from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.stats_dtos import StatsDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.get_stats import GetStatsUseCase

router = APIRouter(tags=["stats"])


@router.get("/stats")
def get_stats(
    stats: GetStatsUseCase = Depends(use_case(Container.get_stats_use_case)),  # noqa: B008
) -> StatsDTO:
    return stats.execute()
