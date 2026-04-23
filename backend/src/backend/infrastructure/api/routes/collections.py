from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.collection_dtos import (  # noqa: TC001
    CollectionDTO,
    CreateCollectionRequest,
    RenameCollectionRequest,
)
from backend.domain.exceptions import CollectionNameExistsError, CollectionNotFoundError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("", status_code=201)
def create_collection(
    request: CreateCollectionRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CollectionDTO:
    try:
        use_case = container.create_collection_use_case(session)
        result = use_case.execute(request.name)
        session.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CollectionNameExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("")
def list_collections(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[CollectionDTO]:
    use_case = container.list_collections_use_case(session)
    return use_case.execute()


@router.patch("/{collection_id}")
def rename_collection(
    collection_id: int,
    request: RenameCollectionRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> CollectionDTO:
    try:
        use_case = container.rename_collection_use_case(session)
        result = use_case.execute(collection_id, request.name)
        session.commit()
        return result
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CollectionNameExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> None:
    try:
        use_case = container.delete_collection_use_case(session)
        use_case.execute(collection_id)
        session.commit()
    except CollectionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
