from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.bootstrap_dtos import (
    BootstrapStatusDTO,
    BootstrapWordDTO,  # noqa: TC001
    GetBootstrapWordsRequest,
    SaveBootstrapWordsRequest,
)
from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/api/bootstrap", tags=["bootstrap"])

_build_task: asyncio.Task[None] | None = None


@router.get("/status")
def get_bootstrap_status(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> BootstrapStatusDTO:
    from backend.infrastructure.persistence.sqla_bootstrap_index_repository import (
        SqlaBootstrapIndexRepository,
    )

    repo = SqlaBootstrapIndexRepository(session)
    meta = repo.get_meta()
    return BootstrapStatusDTO(
        status=meta.status.value,
        error=meta.error,
        built_at=meta.built_at,
        word_count=meta.word_count,
    )


@router.post("/build", status_code=202)
def start_bootstrap_build(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    global _build_task  # noqa: PLW0603

    from backend.infrastructure.persistence.sqla_bootstrap_index_repository import (
        SqlaBootstrapIndexRepository,
    )

    repo = SqlaBootstrapIndexRepository(session)
    meta = repo.get_meta()
    if meta.status is BootstrapIndexStatus.BUILDING:
        raise HTTPException(status_code=409, detail="Build already in progress")

    def _run_build() -> None:
        with container.session_scope() as build_session:
            use_case = container.build_bootstrap_index_use_case(build_session)
            use_case.execute()

    _build_task = asyncio.create_task(asyncio.to_thread(_run_build))
    return {"status": "started"}


@router.post("/words")
def get_bootstrap_words(
    request: GetBootstrapWordsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[BootstrapWordDTO]:
    use_case = container.get_bootstrap_words_use_case(session)
    return use_case.execute(excluded_lemmas=request.excluded)


@router.post("/known")
def save_bootstrap_known(
    request: SaveBootstrapWordsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    use_case = container.manage_known_words_use_case(session)
    use_case.add_bulk(request.lemmas)
    session.commit()
    return {"saved": len(request.lemmas)}
