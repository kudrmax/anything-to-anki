from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import CollectionDTO
from backend.domain.exceptions import CollectionNameExistsError, CollectionNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository

_MAX_NAME_LENGTH: int = 200


class RenameCollectionUseCase:
    """Renames an existing collection."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(self, collection_id: int, new_name: str) -> CollectionDTO:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Collection name must not be empty")
        if len(new_name) > _MAX_NAME_LENGTH:
            raise ValueError(f"Collection name must not exceed {_MAX_NAME_LENGTH} characters")

        existing = self._collection_repo.get_by_id(collection_id)
        if existing is None:
            raise CollectionNotFoundError(collection_id)

        all_collections = self._collection_repo.list_all()
        if any(c.name == new_name and c.id != collection_id for c in all_collections):
            raise CollectionNameExistsError(new_name)

        updated = self._collection_repo.rename(collection_id, new_name)
        return CollectionDTO(
            id=updated.id,  # type: ignore[arg-type]
            name=updated.name,
            source_count=0,  # caller can refetch if needed
            created_at=updated.created_at,
        )
