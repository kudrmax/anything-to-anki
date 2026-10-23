from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.application.utils.source_progress import SourceProgress
from backend.application.utils.topic_generation import TopicGeneration
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository

if TYPE_CHECKING:
    from backend.application.dto.collection_dtos import CollectionTreeDTO


def _progress(by_source: dict[int, DecisionProgress] | None = None) -> MagicMock:
    """Each source has as many cards as its progress counts, and that progress."""
    found = by_source or {}
    progress = MagicMock()
    progress.of_sources.side_effect = lambda source_ids: {
        source_id: SourceProgress(
            found.get(source_id, DecisionProgress()),
            found.get(source_id, DecisionProgress()).total,
        )
        for source_id in source_ids
    }
    return progress


def _card_query(learn_counts: dict[int, int] | None = None) -> MagicMock:
    card_query = MagicMock()
    card_query.learn_counts.return_value = learn_counts or {}
    return card_query


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
            Source(id=10, status=SourceStatus.DONE, collection_id=1),
            Source(id=11, status=SourceStatus.NEW, collection_id=2),
            Source(id=12, status=SourceStatus.ERROR, collection_id=None),
        ]),
        _progress({10: DecisionProgress(decided=2, total=2)}),
        probe,
        _free(),
        _card_query(),
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
        _card_query(),
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
        _card_query(),
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
        _card_query(),
    ).execute()
    assert tree.all.pending == 1


@pytest.mark.unit
def test_a_source_counts_as_reviewed_by_its_progress_when_read() -> None:
    """Every card done: reviewed; one left: not; nothing stored decides it."""
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    use_case = ListCollectionsUseCase(
        InMemoryCollectionRepository([]),
        InMemorySourceRepository([
            Source(id=10, status=SourceStatus.DONE),
            Source(id=11, status=SourceStatus.DONE),
            Source(id=12, status=SourceStatus.DONE),
        ]),
        _progress({
            10: DecisionProgress(decided=3, total=3),
            11: DecisionProgress(decided=2, total=3),
            12: DecisionProgress(decided=0, total=3),
        }),
        probe,
        _free(),
        _card_query(),
    )

    assert use_case.execute().all.reviewed == 1


def _use_case(
    sources: list[Source], progress: dict[int, DecisionProgress],
) -> ListCollectionsUseCase:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    return ListCollectionsUseCase(
        InMemoryCollectionRepository([Collection(id=1, name="Friends")]),
        InMemorySourceRepository(sources),
        _progress(progress),
        probe,
        _free(),
        _card_query({10: 2}),
    )


@pytest.mark.unit
def test_collection_carries_review_state() -> None:
    tree = _use_case(
        sources=[
            Source(id=10, status=SourceStatus.DONE, collection_id=1),
            Source(id=11, status=SourceStatus.ERROR, collection_id=1),
            Source(id=12, status=SourceStatus.DONE, collection_id=None),
        ],
        progress={10: DecisionProgress(decided=1, total=4)},
    ).execute()
    friends = tree.collections[0].counts
    assert (friends.status, friends.can_review) == ("partially_reviewed", True)
    assert friends.review_fraction == 0.25
    assert friends.progress_caption == "1 of 4 decided"
    assert tree.unsorted.can_review is False
    assert tree.all.can_review is True


@pytest.mark.unit
def test_a_set_reads_like_its_sources() -> None:
    """Every source failed: the set failed; nothing processed: new; empty: new."""
    failed = _use_case(
        sources=[
            Source(id=10, status=SourceStatus.ERROR, collection_id=1),
            Source(id=11, status=SourceStatus.ERROR, collection_id=1),
        ],
        progress={},
    ).execute().collections[0].counts
    assert (failed.status, failed.can_review, failed.progress_caption) == (
        "error", False, "Nothing to learn",
    )
    empty = _use_case(sources=[], progress={}).execute().collections[0].counts
    assert (empty.status, empty.can_review, empty.review_fraction) == ("new", False, 0.0)


@pytest.mark.unit
def test_a_reviewed_set_counts_its_words_to_learn() -> None:
    reviewed = _use_case(
        sources=[Source(id=10, status=SourceStatus.DONE, collection_id=1)],
        progress={10: DecisionProgress(decided=3, total=3)},
    ).execute().collections[0].counts
    assert (reviewed.status, reviewed.review_fraction) == ("reviewed", 1.0)
    assert reviewed.progress_caption == "2 to learn"


def _held(operations: dict[int, HeldOperation]) -> MagicMock:
    lock = MagicMock()
    lock.operations.return_value = operations
    return lock


def _tree_of(
    sources: list[Source], lock: MagicMock, *, awaiting: bool = False,
) -> CollectionTreeDTO:
    probe = MagicMock()
    probe.of.return_value = TopicGeneration(awaiting=awaiting)
    return ListCollectionsUseCase(
        InMemoryCollectionRepository([Collection(id=1, name="Friends")]),
        InMemorySourceRepository(sources),
        _progress(),
        probe,
        lock,
        _card_query(),
    ).execute()


@pytest.mark.unit
def test_a_set_with_a_source_in_a_preview_reads_as_its_sources() -> None:
    tree = _tree_of(
        [
            Source(id=10, status=SourceStatus.NEW, collection_id=1),
            Source(id=11, status=SourceStatus.ERROR, collection_id=1),
        ],
        _held({10: HeldOperation(SourceOperationKind.PREVIEW)}),
    )
    friends = tree.collections[0].counts
    assert (friends.status, friends.pending, friends.can_process) == ("new", 1, True)


@pytest.mark.unit
def test_a_set_with_nothing_to_start_cannot_be_processed() -> None:
    held = _tree_of(
        [Source(id=10, status=SourceStatus.NEW, collection_id=1)],
        _held({10: HeldOperation(SourceOperationKind.PREVIEW)}),
    ).collections[0].counts
    assert (held.status, held.can_process) == ("new", False)
    empty = _tree_of([], _held({})).collections[0].counts
    assert (empty.status, empty.can_process) == ("new", False)
    awaiting = _tree_of(
        [Source(id=10, status=SourceStatus.NEW, collection_id=1)], _held({}), awaiting=True,
    ).collections[0].counts
    assert (awaiting.status, awaiting.can_process) == ("new", False)


@pytest.mark.unit
def test_a_processed_set_keeps_its_review_status_while_another_source_is_processed() -> None:
    tree = _tree_of(
        [
            Source(id=10, status=SourceStatus.DONE, collection_id=1),
            Source(id=11, status=SourceStatus.NEW, collection_id=1),
        ],
        _held({11: HeldOperation(SourceOperationKind.PROCESS)}),
    )
    friends = tree.collections[0].counts
    assert (friends.status, friends.can_process) == ("reviewed", False)


@pytest.mark.unit
def test_a_set_offers_the_operations_of_its_sources_and_export() -> None:
    reviewed = _use_case(
        sources=[Source(id=10, status=SourceStatus.DONE, collection_id=1)],
        progress={10: DecisionProgress(decided=3, total=3)},
    ).execute()
    friends = reviewed.collections[0].counts
    assert friends.available_operations == [SourceOperationKind.UPDATE, SourceOperationKind.RECUT]
    assert (friends.can_start_operation, friends.operation_hint) == (True, None)
    assert friends.can_export is True
    assert (reviewed.unsorted.available_operations, reviewed.unsorted.can_export) == ([], False)


@pytest.mark.unit
def test_a_set_whose_every_rebuildable_source_is_busy_cannot_start() -> None:
    friends = _tree_of(
        [
            Source(id=10, status=SourceStatus.DONE, collection_id=1),
            Source(id=11, status=SourceStatus.NEW, collection_id=1),
        ],
        _held({10: HeldOperation(SourceOperationKind.UPDATE)}),
    ).collections[0].counts
    assert friends.available_operations == [SourceOperationKind.UPDATE, SourceOperationKind.RECUT]
    assert friends.can_start_operation is False
    assert friends.operation_hint == "Wait until the word search finishes"
