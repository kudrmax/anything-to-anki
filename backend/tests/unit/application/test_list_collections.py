from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.application.utils.topic_generation import TopicGeneration
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def _progress(by_source: dict[int, DecisionProgress] | None = None) -> MagicMock:
    progress = MagicMock()
    progress.of_sources.side_effect = lambda source_ids: {
        source_id: (by_source or {}).get(source_id, DecisionProgress())
        for source_id in source_ids
    }
    return progress


def _free() -> MagicMock:
    lock = MagicMock()
    lock.operations.return_value = {}
    return lock


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
        _progress(),
        probe,
        _free(),
    )

    tree = use_case.execute()

    assert (tree.all.total, tree.all.reviewed, tree.all.pending) == (3, 1, 2)
    assert (tree.unsorted.total, tree.unsorted.pending) == (1, 1)
    friends, ielts = tree.collections
    assert friends.name == "Friends"
    assert (friends.counts.total, friends.counts.reviewed, friends.counts.pending) == (2, 1, 1)
    assert (friends.depth, friends.accepts_collections) == (1, True)
    assert friends.move_targets == [None, 3]
    assert ielts.move_targets == [None, 1, 2]
    (season,) = friends.children
    assert season.counts.total == 1
    assert (season.depth, season.accepts_collections) == (2, True)
    assert tree.max_depth == 5


@pytest.mark.unit
def test_tree_of_full_depth() -> None:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    chain = [
        Collection(id=i, name=f"L{i}", parent_id=i - 1 if i > 1 else None) for i in range(1, 6)
    ]
    tree = ListCollectionsUseCase(
        InMemoryCollectionRepository(chain),
        InMemorySourceRepository([Source(id=10, status=SourceStatus.NEW, collection_id=5)]),
        _progress(),
        probe,
        _free(),
    ).execute()

    levels = []
    node = tree.collections[0]
    while True:
        levels.append(node)
        if not node.children:
            break
        (node,) = node.children
    assert [n.depth for n in levels] == [1, 2, 3, 4, 5]
    assert [n.accepts_collections for n in levels] == [True, True, True, True, False]
    assert all(n.counts.total == 1 for n in levels)
    assert levels[4].move_targets == [None, 1, 2, 3, 4]
    assert levels[0].move_targets == [None]


@pytest.mark.unit
def test_progress_sums_the_progress_of_sources_of_the_whole_subtree() -> None:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    tree = ListCollectionsUseCase(
        InMemoryCollectionRepository([
            Collection(id=1, name="Books"),
            Collection(id=2, name="Twig", parent_id=1),
            Collection(id=3, name="Empty", parent_id=1, position=1),
        ]),
        InMemorySourceRepository([
            Source(id=10, status=SourceStatus.NEW, collection_id=1),
            Source(id=11, status=SourceStatus.NEW, collection_id=2),
            Source(id=12, status=SourceStatus.NEW, collection_id=None),
        ]),
        _progress({
            10: DecisionProgress(decided=2, total=963),
            11: DecisionProgress(decided=39, total=107),
            12: DecisionProgress(decided=4, total=4),
        }),
        probe,
        _free(),
    ).execute()

    (books,) = tree.collections
    twig, empty = books.children
    assert (books.counts.progress.decided, books.counts.progress.total) == (41, 1070)
    assert (twig.counts.progress.decided, twig.counts.progress.total) == (39, 107)
    assert (empty.counts.progress.decided, empty.counts.progress.total) == (0, 0)
    assert (tree.unsorted.progress.decided, tree.unsorted.progress.total) == (4, 4)
    assert (tree.all.progress.decided, tree.all.progress.total) == (45, 1074)


@pytest.mark.unit
def test_a_source_being_processed_is_not_pending() -> None:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    lock = _free()
    lock.operations.return_value = {10: HeldOperation(SourceOperationKind.PROCESS)}
    tree = ListCollectionsUseCase(
        InMemoryCollectionRepository([]),
        InMemorySourceRepository([
            Source(id=10, status=SourceStatus.NEW), Source(id=11, status=SourceStatus.NEW),
        ]),
        _progress(),
        probe,
        lock,
    ).execute()
    assert tree.all.pending == 1
