from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import CollectionDTO
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionNameExistsError

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository

_MAX_NAME_LENGTH: int = 200


class CreateCollectionUseCase:
    """Creates a new collection."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(self, name: str) -> CollectionDTO:
        name = name.strip()
        if not name:
            raise ValueError("Collection name must not be empty")
        if len(name) > _MAX_NAME_LENGTH:
            raise ValueError(f"Collection name must not exceed {_MAX_NAME_LENGTH} characters")

        existing = self._collection_repo.list_all()
        if any(c.name == name for c in existing):
            raise CollectionNameExistsError(name)

        collection = self._collection_repo.create(Collection(name=name))
        return CollectionDTO(
            id=collection.id,  # type: ignore[arg-type]
            name=collection.name,
            source_count=0,
            created_at=collection.created_at,
        )
