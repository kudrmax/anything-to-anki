from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.application.utils.topic_generation import TopicGeneration
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


@pytest.mark.unit
def test_tree_with_subtree_counts_and_drag_hints() -> None:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    use_case = ListCollectionsUseCase(
        InMemoryCollectionRepository([
            Collection(id=1, name="Friends", position=0),
            Collection(id=2, name="Season 1", parent_id=1),
            Collection(id=3, name="IELTS", position=1),
        ]),
        InMemorySourceRepository([
            Source(id=10, status=SourceStatus.REVIEWED, collection_id=1),
            Source(id=11, status=SourceStatus.NEW, collection_id=2),
            Source(id=12, status=SourceStatus.ERROR, collection_id=None),
        ]),
        probe,
    )

    tree = use_case.execute()

    assert (tree.all.total, tree.all.reviewed, tree.all.pending) == (3, 1, 2)
    assert (tree.unsorted.total, tree.unsorted.pending) == (1, 1)
    friends, ielts = tree.collections
    assert friends.name == "Friends"
    assert (friends.counts.total, friends.counts.reviewed, friends.counts.pending) == (2, 1, 1)
    assert (friends.accepts_collections, friends.can_be_nested) == (True, False)
    assert (ielts.accepts_collections, ielts.can_be_nested) == (True, True)
    (season,) = friends.children
    assert season.counts.total == 1
    assert (season.accepts_collections, season.can_be_nested) == (False, True)
