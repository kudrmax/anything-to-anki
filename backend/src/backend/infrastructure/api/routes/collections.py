from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.collection_dtos import (  # noqa: TC001
    CollectionDTO,
    CollectionTreeDTO,
    CreateCollectionRequest,
    DeletedCollectionDTO,
    MoveCollectionRequest,
    MovedCollectionDTO,
    RenameCollectionRequest,
    RenamedCollectionDTO,
)
from backend.domain.exceptions import (
    CollectionMoveNotAllowedError,
    CollectionNameExistsError,
    CollectionNotFoundError,
)
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])

_STATUS_BY_ERROR: tuple[tuple[type[Exception], int], ...] = (
    (CollectionNotFoundError, 404),
    (CollectionNameExistsError, 409),
    (CollectionMoveNotAllowedError, 409),
    (ValueError, 400),
)
_HANDLED = (
    CollectionNotFoundError,
    CollectionNameExistsError,
    CollectionMoveNotAllowedError,
    ValueError,
)


def _http_error(error: Exception) -> HTTPException:
    status = next(code for kind, code in _STATUS_BY_ERROR if isinstance(error, kind))
    return HTTPException(status_code=status, detail=str(error))


@router.get("")
def list_collections(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CollectionTreeDTO:
    return container.list_collections_use_case(session).execute()


@router.post("", status_code=201)
def create_collection(
    request: CreateCollectionRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CollectionDTO:
    try:
        result = container.create_collection_use_case(session).execute(
            request.name, request.parent_id,
        )
        session.commit()
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.patch("/{collection_id}")
def rename_collection(
    collection_id: int,
    request: RenameCollectionRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> RenamedCollectionDTO:
    try:
        result = container.rename_collection_use_case(session).execute(collection_id, request.name)
        session.commit()
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.post("/{collection_id}/move")
def move_collection(
    collection_id: int,
    request: MoveCollectionRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> MovedCollectionDTO:
    try:
        result = container.move_collection_use_case(session).execute(
            collection_id, request.parent_id, request.position,
        )
        session.commit()
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.delete("/{collection_id}")
def delete_collection(
    collection_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> DeletedCollectionDTO:
    try:
        result = container.delete_collection_use_case(session).execute(collection_id)
        session.commit()
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.post("/{collection_id}/restore")
def restore_collection(
    collection_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CollectionDTO:
    try:
        result = container.restore_collection_use_case(session).execute(collection_id)
        session.commit()
        return result
    except _HANDLED as e:
        raise _http_error(e) from e
