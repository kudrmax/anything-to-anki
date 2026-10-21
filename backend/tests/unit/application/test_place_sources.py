from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.dto.collection_dtos import SourcePlacementDTO
from backend.application.use_cases.place_sources import PlaceSourcesUseCase
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import CollectionNotFoundError, SourceNotFoundError
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


@pytest.mark.unit
class TestPlaceSources:
    def setup_method(self) -> None:
        self.sources = InMemorySourceRepository([
            Source(id=1, status=SourceStatus.NEW, collection_id=None),
            Source(id=2, status=SourceStatus.NEW, collection_id=5),
        ])
        self.collections = InMemoryCollectionRepository([
            Collection(id=5, name="IELTS"), Collection(id=6, name="Worm", position=1),
        ])
        self.use_case = PlaceSourcesUseCase(self.sources, self.collections, MagicMock())

    def test_moves_batch_and_answers_previous_places(self) -> None:
        placed = self.use_case.execute([
            SourcePlacementDTO(source_id=1, collection_id=6),
            SourcePlacementDTO(source_id=2, collection_id=6),
        ])
        assert placed.previous == [
            SourcePlacementDTO(source_id=1, collection_id=None),
            SourcePlacementDTO(source_id=2, collection_id=5),
        ]
        assert {s.collection_id for s in self.sources.items.values()} == {6}

        self.use_case.execute(placed.previous)
        restored = (self.sources.items[1].collection_id, self.sources.items[2].collection_id)
        assert restored == (None, 5)

    def test_unknown_collection_changes_nothing(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            self.use_case.execute([SourcePlacementDTO(source_id=1, collection_id=99)])
        assert self.sources.items[1].collection_id is None

    def test_unknown_source(self) -> None:
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute([SourcePlacementDTO(source_id=42, collection_id=None)])
