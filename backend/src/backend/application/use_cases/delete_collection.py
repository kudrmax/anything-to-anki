from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CollectionNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository


class DeleteCollectionUseCase:
    """Deletes a collection. Sources are NOT deleted — they become uncategorized (ON DELETE SET NULL)."""

    def __init__(self, collection_repo: CollectionRepository) -> None:
        self._collection_repo = collection_repo

    def execute(self, collection_id: int) -> None:
        existing = self._collection_repo.get_by_id(collection_id)
        if existing is None:
            raise CollectionNotFoundError(collection_id)
        self._collection_repo.delete(collection_id)
