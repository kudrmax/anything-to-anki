from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.bootstrap_dtos import (  # noqa: TC001
    BootstrapStatusDTO,
    BootstrapWordDTO,
    GetBootstrapWordsRequest,
    SaveBootstrapWordsRequest,
)
from backend.infrastructure.api.dependencies import (
    DetachedUseCases,
    get_detached_use_cases,
    use_case,
)
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.build_bootstrap_index import BuildBootstrapIndexUseCase
    from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
    from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase

router = APIRouter(prefix="/api/bootstrap", tags=["bootstrap"])

_build_task: asyncio.Task[None] | None = None


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
) -> dict[str, str]:
    global _build_task  # noqa: PLW0603

    if build.is_building():
        raise HTTPException(status_code=409, detail="Build already in progress")

    def _run_build() -> None:
        with detached.open(Container.build_bootstrap_index_use_case) as background_build:
            background_build.execute()

    _build_task = asyncio.create_task(asyncio.to_thread(_run_build))
    return {"status": "started"}


@router.post("/words")
def get_bootstrap_words(
    request: GetBootstrapWordsRequest,
    words: GetBootstrapWordsUseCase = Depends(  # noqa: B008
        use_case(Container.get_bootstrap_words_use_case),  # noqa: B008
    ),
) -> list[BootstrapWordDTO]:
    return words.execute(excluded_lemmas=request.excluded)


@router.post("/known")
def save_bootstrap_known(
    request: SaveBootstrapWordsRequest,
    known_words: ManageKnownWordsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_known_words_use_case),  # noqa: B008
    ),
) -> dict[str, int]:
    known_words.add_bulk(request.lemmas)
    return {"saved": len(request.lemmas)}
