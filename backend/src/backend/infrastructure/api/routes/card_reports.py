from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from backend.application.dto.card_report_dtos import CardReportDTO  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

# Under /api: a plain /card-reports could collide with a frontend route.
router = APIRouter(prefix="/api/card-reports", tags=["card-reports"])


@router.get("")
def list_card_reports(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[CardReportDTO]:
    return container.report_candidate_use_case(session).list_all()


@router.get("/reasons")
def list_report_reasons(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[str]:
    return container.report_candidate_use_case(session).reasons()
