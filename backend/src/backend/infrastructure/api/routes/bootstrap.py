from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.bootstrap_dtos import (  # noqa: TC001
    BootstrapStatusDTO,
    BootstrapWordDTO,
    CalibrationSkippedWordsDTO,
    GetBootstrapWordsRequest,
    SaveCalibrationRoundRequest,
)
from backend.domain.exceptions import LongOperationInProgressError
from backend.infrastructure.api.dependencies import (
    DetachedUseCases,
    get_container,
    get_detached_use_cases,
    use_case,
)
from backend.infrastructure.api.running_operations import BOOTSTRAP_BUILDS
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.build_bootstrap_index import BuildBootstrapIndexUseCase
    from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
    from backend.application.use_cases.manage_calibration_skipped_words import (
        ManageCalibrationSkippedWordsUseCase,
    )
    from backend.application.use_cases.save_calibration_round import SaveCalibrationRoundUseCase

router = APIRouter(prefix="/api/bootstrap", tags=["bootstrap"])

@router.get("/status")
def get_bootstrap_status(
    build: BuildBootstrapIndexUseCase = Depends(  # noqa: B008
        use_case(Container.build_bootstrap_index_use_case),  # noqa: B008
    ),
) -> BootstrapStatusDTO:
    return build.status()


@router.post("/build", status_code=202)
async def start_bootstrap_build(
    build: BuildBootstrapIndexUseCase = Depends(  # noqa: B008
        use_case(Container.build_bootstrap_index_use_case),  # noqa: B008
    ),
    detached: DetachedUseCases = Depends(get_detached_use_cases),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    if container.long_operation_progress().status().running:
        raise LongOperationInProgressError
    if build.is_building() or BOOTSTRAP_BUILDS.running():
        raise HTTPException(status_code=409, detail="Build already in progress")

    def _run_build() -> None:
        with detached.open(Container.build_bootstrap_index_use_case) as background_build:
            background_build.execute()

    BOOTSTRAP_BUILDS.track(asyncio.create_task(asyncio.to_thread(_run_build)))
    return {"status": "started"}


@router.post("/words")
def get_bootstrap_words(
    request: GetBootstrapWordsRequest,
    words: GetBootstrapWordsUseCase = Depends(  # noqa: B008
        use_case(Container.get_bootstrap_words_use_case),  # noqa: B008
    ),
) -> list[BootstrapWordDTO]:
    return words.execute(order=request.order)


@router.post("/round", status_code=204)
def save_calibration_round(
    request: SaveCalibrationRoundRequest,
    round_: SaveCalibrationRoundUseCase = Depends(  # noqa: B008
        use_case(Container.save_calibration_round_use_case),  # noqa: B008
    ),
) -> None:
    round_.execute(shown=request.shown, known=request.known)


@router.get("/skipped")
def get_calibration_skipped_words(
    skipped: ManageCalibrationSkippedWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_calibration_skipped_words_use_case),  # noqa: B008
    ),
) -> CalibrationSkippedWordsDTO:
    return skipped.summary()


@router.delete("/skipped", status_code=204)
def forget_calibration_skipped_words(
    skipped: ManageCalibrationSkippedWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_calibration_skipped_words_use_case),  # noqa: B008
    ),
) -> None:
    skipped.forget()
