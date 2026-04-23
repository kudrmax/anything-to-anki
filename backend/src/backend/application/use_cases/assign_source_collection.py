from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CollectionNotFoundError, SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository


class AssignSourceToCollectionUseCase:
    """Assigns a source to a collection, or removes it from any collection."""

    def __init__(
        self,
        source_repo: SourceRepository,
        collection_repo: CollectionRepository,
    ) -> None:
        self._source_repo = source_repo
        self._collection_repo = collection_repo

    def execute(self, source_id: int, collection_id: int | None) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)

        if collection_id is not None:
            collection = self._collection_repo.get_by_id(collection_id)
            if collection is None:
                raise CollectionNotFoundError(collection_id)

        self._source_repo.update_collection(source_id, collection_id)
