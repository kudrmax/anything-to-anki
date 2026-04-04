from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.source_dtos import (  # noqa: TC001
    CreateSourceRequest,
    SourceDetailDTO,
    SourceDTO,
)
from backend.domain.exceptions import SourceAlreadyProcessedError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", status_code=201)
def create_source(
    request: CreateSourceRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    try:
        use_case = container.create_source_use_case(session)
        source = use_case.execute(request.raw_text)
        session.commit()
        return {"id": source.id, "status": source.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def list_sources(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[SourceDTO]:
    use_case = container.get_sources_use_case(session)
    return use_case.list_all()


@router.get("/{source_id}")
def get_source(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SourceDetailDTO:
    try:
        use_case = container.get_sources_use_case(session)
        return use_case.get_by_id(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{source_id}/process", status_code=202)
async def process_source(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: object = Depends(get_session_factory),  # noqa: B008
) -> dict[str, str]:
    try:
        use_case = container.process_source_use_case(session)
        use_case.start(source_id)
        session.commit()
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceAlreadyProcessedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    asyncio.create_task(_process_background(source_id, container, session_factory))
    return {"status": "processing"}


async def _process_background(
    source_id: int,
    container: Container,
    session_factory: object,
) -> None:
    bg_session: Session = session_factory()  # type: ignore[operator]
    try:
        use_case = container.process_source_use_case(bg_session)
        await asyncio.to_thread(use_case.execute, source_id)
        bg_session.commit()
    except Exception:
        bg_session.rollback()
        # Mark source as ERROR in a fresh session
        err_session: Session = session_factory()  # type: ignore[operator]
        try:
            from backend.infrastructure.persistence.sqla_source_repository import (
                SqlaSourceRepository,
            )
            repo = SqlaSourceRepository(err_session)
            repo.update_status(source_id, SourceStatus.ERROR, error_message="Processing failed")
            err_session.commit()
        except Exception:
            logger.exception("Failed to mark source %d as ERROR", source_id)
            err_session.rollback()
        finally:
            err_session.close()
    finally:
        bg_session.close()


@router.get("/{source_id}/candidates")
def get_candidates(
    source_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[dict[str, Any]]:
    try:
        use_case = container.get_candidates_use_case(session)
        candidates = use_case.execute(source_id)
        return [c.model_dump() for c in candidates]
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
