from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import CollectionDTO

if TYPE_CHECKING:
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository


class ListCollectionsUseCase:
    """Lists all collections with source counts."""

    def __init__(
        self,
        collection_repo: CollectionRepository,
        source_repo: SourceRepository,
    ) -> None:
        self._collection_repo = collection_repo
        self._source_repo = source_repo

    def execute(self) -> list[CollectionDTO]:
        collections = self._collection_repo.list_all()
        all_sources = self._source_repo.list_all()

        counts: dict[int, int] = {}
        for source in all_sources:
            if source.collection_id is not None:
                counts[source.collection_id] = counts.get(source.collection_id, 0) + 1

        result: list[CollectionDTO] = []
        for c in sorted(collections, key=lambda x: x.name.lower()):
            result.append(
                CollectionDTO(
                    id=c.id,  # type: ignore[arg-type]
                    name=c.name,
                    source_count=counts.get(c.id, 0),  # type: ignore[arg-type]
                    created_at=c.created_at,
                )
            )
        return result
