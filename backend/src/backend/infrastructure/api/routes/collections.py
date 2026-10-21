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
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.create_collection import CreateCollectionUseCase
    from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
    from backend.application.use_cases.favorite_collection import FavoriteCollectionUseCase
    from backend.application.use_cases.list_collections import ListCollectionsUseCase
    from backend.application.use_cases.move_collection import MoveCollectionUseCase
    from backend.application.use_cases.rename_collection import RenameCollectionUseCase
    from backend.application.use_cases.restore_collection import RestoreCollectionUseCase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])

_STATUS_BY_ERROR: tuple[tuple[type[Exception], int], ...] = (
    (CollectionNotFoundError, 404),
    (CollectionNameExistsError, 409),
    (CollectionMoveNotAllowedError, 409),
    (ValueError, 400),
)
_HANDLED = tuple(kind for kind, _ in _STATUS_BY_ERROR)


def _http_error(error: Exception) -> HTTPException:
    status = next(code for kind, code in _STATUS_BY_ERROR if isinstance(error, kind))
    return HTTPException(status_code=status, detail=str(error))


@router.get("")
def list_collections(
    collections: ListCollectionsUseCase = Depends(  # noqa: B008
        use_case(Container.list_collections_use_case),  # noqa: B008
    ),
) -> CollectionTreeDTO:
    return collections.execute()


@router.post("", status_code=201)
def create_collection(
    request: CreateCollectionRequest,
    create: CreateCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.create_collection_use_case),  # noqa: B008
    ),
) -> CollectionDTO:
    try:
        result = create.execute(
            request.name, request.parent_id,
        )
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.patch("/{collection_id}")
def rename_collection(
    collection_id: int,
    request: RenameCollectionRequest,
    rename: RenameCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.rename_collection_use_case),  # noqa: B008
    ),
) -> RenamedCollectionDTO:
    try:
        result = rename.execute(collection_id, request.name)
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.post("/{collection_id}/move")
def move_collection(
    collection_id: int,
    request: MoveCollectionRequest,
    move: MoveCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.move_collection_use_case),  # noqa: B008
    ),
) -> MovedCollectionDTO:
    try:
        result = move.execute(
            collection_id, request.parent_id, request.position,
        )
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.put("/{collection_id}/favorite", status_code=204)
def add_to_favorites(
    collection_id: int,
    favorite: FavoriteCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.favorite_collection_use_case),  # noqa: B008
    ),
) -> None:
    try:
        favorite.execute(collection_id, favorite=True)
    except _HANDLED as e:
        raise _http_error(e) from e

@router.delete("/{collection_id}/favorite", status_code=204)
def remove_from_favorites(
    collection_id: int,
    favorite: FavoriteCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.favorite_collection_use_case),  # noqa: B008
    ),
) -> None:
    try:
        favorite.execute(collection_id, favorite=False)
    except _HANDLED as e:
        raise _http_error(e) from e

@router.delete("/{collection_id}")
def delete_collection(
    collection_id: int,
    delete: DeleteCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.delete_collection_use_case),  # noqa: B008
    ),
) -> DeletedCollectionDTO:
    try:
        result = delete.execute(collection_id)
        return result
    except _HANDLED as e:
        raise _http_error(e) from e

@router.post("/{collection_id}/restore")
def restore_collection(
    collection_id: int,
    restore: RestoreCollectionUseCase = Depends(  # noqa: B008
        use_case(Container.restore_collection_use_case),  # noqa: B008
    ),
) -> CollectionDTO:
    try:
        result = restore.execute(collection_id)
        return result
    except _HANDLED as e:
        raise _http_error(e) from e
