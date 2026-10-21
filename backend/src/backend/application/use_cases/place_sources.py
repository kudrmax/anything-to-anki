from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import PlacedSourcesDTO, SourcePlacementDTO
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.collection_tree import CollectionTree

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork


class PlaceSourcesUseCase:
    """Puts sources into collections (or Unsorted) in one go; their previous places come back,
    so the same call with that answer is Undo."""

    def __init__(
        self, source_repo: SourceRepository, collection_repo: CollectionRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._source_repo = source_repo
        self._collection_repo = collection_repo

    def execute(self, placements: Sequence[SourcePlacementDTO]) -> PlacedSourcesDTO:
        with self._unit_of_work.write():
            return self._place(placements)

    def _place(self, placements: Sequence[SourcePlacementDTO]) -> PlacedSourcesDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        for placement in placements:
            if placement.collection_id is not None:
                tree.get(placement.collection_id)
        previous: list[SourcePlacementDTO] = []
        for placement in placements:
            source = self._source_repo.get_by_id(placement.source_id)
            if source is None:
                raise SourceNotFoundError(placement.source_id)
            previous.append(SourcePlacementDTO(
                source_id=placement.source_id, collection_id=source.collection_id,
            ))
        self._source_repo.set_collections({p.source_id: p.collection_id for p in placements})
        return PlacedSourcesDTO(previous=previous)
