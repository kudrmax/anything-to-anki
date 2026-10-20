from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.card_report_dtos import (  # noqa: TC001
    CardReportDTO,
    ReportReasonDTO,
)
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.report_candidate import ReportCandidateUseCase

# Under /api: a plain /card-reports could collide with a frontend route.
router = APIRouter(prefix="/api/card-reports", tags=["card-reports"])


@router.get("")
def list_card_reports(
    reports: ReportCandidateUseCase = Depends(  # noqa: B008
        use_case(Container.report_candidate_use_case),  # noqa: B008
    ),
) -> list[CardReportDTO]:
    return reports.list_all()


@router.get("/reasons")
def list_report_reasons(
    reports: ReportCandidateUseCase = Depends(  # noqa: B008
        use_case(Container.report_candidate_use_case),  # noqa: B008
    ),
) -> list[ReportReasonDTO]:
    return reports.reasons()
