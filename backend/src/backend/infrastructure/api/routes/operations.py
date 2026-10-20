from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, sessionmaker  # noqa: TC002 — FastAPI reads route annotations

from backend.application.dto.rebuild_dtos import SourceOperationDTO  # noqa: TC001
from backend.domain.exceptions import (
    CollectionNotFoundError,
    RebuildNotSupportedError,
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.services.source_operations import REBUILD_OPERATION
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.background import in_background, operation_background
from backend.infrastructure.api.dependencies import (
    get_container,
    get_db_session,
    get_session_factory,
)
from backend.infrastructure.api.scope_param import parse_scope
from backend.infrastructure.api.source_operations import OPERATIONS

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from backend.application.use_cases.scope_operation import ScopeOperationUseCase
    from backend.domain.value_objects.source_scope import SourceScope
    from backend.infrastructure.container import Container

# Under /api: the web app owns the other paths.
router = APIRouter(prefix="/api/operations", tags=["operations"])


@contextmanager
def _check_errors() -> Iterator[None]:
    """Nothing in the set offers the operation: 400; every source offering it is busy:
    409; a source or collection that is gone: 404."""
    try:
        yield
    except (RebuildNotSupportedError, RefreshNotSupportedError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (SourceNotFoundError, CollectionNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _start(
    raw_scope: str,
    kind: SourceOperationKind,
    offered: SourceOperationKind,
    session: Session,
    container: Container,
    session_factory: sessionmaker[Session],
    run: Callable[[ScopeOperationUseCase, SourceScope, int], None],
) -> SourceOperationDTO:
    """Checks the set synchronously — some source offers it as `offered` and is free —
    then runs the operation in the background."""
    scope = parse_scope(raw_scope)
    with _check_errors():
        container.scope_operation_use_case(session).check(scope, offered)
    operation = OPERATIONS.started(scope.token, kind)

    def prepare(bg_session: Session) -> Callable[[], None]:
        use_case = container.scope_operation_use_case(bg_session)
        return lambda: run(use_case, scope, operation.operation_id)

    in_background(operation_background(
        OPERATIONS, scope.token, operation.operation_id, session_factory, prepare,
    ))
    return operation


@router.post("/preview", status_code=202)
async def preview(
    scope: str,
    of: RebuildMode,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> SourceOperationDTO:
    """Starts the analysis of an Update or Re-cut of the set; its counts come with the
    operation."""

    def run(use_case: ScopeOperationUseCase, target: SourceScope, operation_id: int) -> None:
        OPERATIONS.finished(target.token, operation_id, preview=use_case.preview(target, of))

    return _start(
        scope, SourceOperationKind.PREVIEW, REBUILD_OPERATION[of], session, container,
        session_factory, run,
    )


def _rebuild(
    scope: str,
    mode: RebuildMode,
    session: Session,
    container: Container,
    session_factory: sessionmaker[Session],
) -> SourceOperationDTO:
    def run(use_case: ScopeOperationUseCase, target: SourceScope, operation_id: int) -> None:
        OPERATIONS.finished(target.token, operation_id, summary=use_case.rebuild(target, mode))

    operation = REBUILD_OPERATION[mode]
    return _start(scope, operation, operation, session, container, session_factory, run)


@router.post("/update", status_code=202)
async def update(
    scope: str,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> SourceOperationDTO:
    return _rebuild(scope, RebuildMode.UPDATE, session, container, session_factory)


@router.post("/recut", status_code=202)
async def recut(
    scope: str,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> SourceOperationDTO:
    return _rebuild(scope, RebuildMode.RECUT, session, container, session_factory)


@router.post("/refresh", status_code=202)
async def refresh(
    scope: str,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
    session_factory: sessionmaker[Session] = Depends(get_session_factory),  # noqa: B008
) -> SourceOperationDTO:
    """Adds to the set's topics the phrases their targets now have in the other sources."""

    def run(use_case: ScopeOperationUseCase, target: SourceScope, operation_id: int) -> None:
        OPERATIONS.finished(target.token, operation_id, refresh=use_case.refresh(target))

    return _start(
        scope, SourceOperationKind.REFRESH, SourceOperationKind.REFRESH, session, container,
        session_factory, run,
    )


@router.get("")
def get_operation(scope: str) -> SourceOperationDTO:
    """The last update, re-cut, preview or refresh started on the set: running, or its
    result."""
    token = parse_scope(scope).token
    operation = OPERATIONS.last(token)
    if operation is None:
        raise HTTPException(status_code=404, detail=f"No operation on {token}")
    return operation
