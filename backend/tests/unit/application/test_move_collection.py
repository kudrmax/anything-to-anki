from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.move_collection import MoveCollectionUseCase
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import CollectionMoveNotAllowedError

from tests.unit.application.collection_fakes import InMemoryCollectionRepository


@pytest.mark.unit
class TestMoveCollection:
    def setup_method(self) -> None:
        self.repo = InMemoryCollectionRepository([
            Collection(id=1, name="Friends", position=0),
            Collection(id=2, name="IELTS", position=1),
            Collection(id=3, name="Dune", position=2),
        ])

    def test_move_into_and_undo(self) -> None:
        use_case = MoveCollectionUseCase(self.repo, MagicMock())
        moved = use_case.execute(3, 2, 0)
        assert (moved.previous_parent_id, moved.previous_position) == (None, 2)
        assert self.repo.items[3].parent_id == 2

        use_case.execute(3, moved.previous_parent_id, moved.previous_position)
        assert self.repo.items[3].parent_id is None
        assert [c.id for c in sorted(self.repo.list_all(), key=lambda c: c.position)] == [1, 2, 3]

    def test_rejects_forbidden_move(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            MoveCollectionUseCase(self.repo, MagicMock()).execute(1, 1, 0)
