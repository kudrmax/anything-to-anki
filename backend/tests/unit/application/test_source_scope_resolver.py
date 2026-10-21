from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_progress import SourceProgress
from backend.application.utils.source_ordering import SourceOrdering
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.application.utils.topic_generation import TopicGeneration
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    CollectionNotFoundError,
    ScopeNotReviewableError,
    SourceNotFoundError,
)
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_order import SourceGrouping, SourceSort
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_stage import SourceStage
from backend.domain.value_objects.source_status import SourceStatus

from tests.source_order_support import added_order, order_settings
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository


def source(source_id: int, collection_id: int | None) -> Source:
    return Source(
        id=source_id, status=SourceStatus.NEW, collection_id=collection_id,
        created_at=datetime(2026, 1, source_id, tzinfo=UTC),
    )


@pytest.mark.unit
class TestSourceScopeResolver:
    def setup_method(self) -> None:
        self.resolver = SourceScopeResolver(
            InMemorySourceRepository([source(1, None), source(2, 1), source(3, 2)]),
            InMemoryCollectionRepository([
                Collection(id=1, name="Friends"), Collection(id=2, name="Season 1", parent_id=1),
            ]),
            added_order(),
        )

    def test_scopes(self) -> None:
        assert [s.id for s in self.resolver.sources(SourceScope.all())] == [3, 2, 1]
        assert [s.id for s in self.resolver.sources(SourceScope.unsorted())] == [1]
        assert [s.id for s in self.resolver.sources(SourceScope.collection(1))] == [3, 2]
        assert [s.id for s in self.resolver.sources(SourceScope.collection(2))] == [3]

    def test_titles(self) -> None:
        assert self.resolver.title(SourceScope.collection(2)) == "Friends / Season 1"
        assert self.resolver.title(SourceScope.unsorted()) == "Unsorted"

    def test_unknown_collection(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            self.resolver.sources(SourceScope.collection(9))

    def test_source_scope_is_that_source(self) -> None:
        assert [s.id for s in self.resolver.sources(SourceScope.source(2))] == [2]

    def test_unknown_source(self) -> None:
        with pytest.raises(SourceNotFoundError):
            self.resolver.sources(SourceScope.source(9))

    def test_source_title(self) -> None:
        resolver = SourceScopeResolver(
            InMemorySourceRepository([Source(id=5, title="Pilot", status=SourceStatus.DONE)]),
            InMemoryCollectionRepository([]),
            added_order(),
        )
        assert resolver.title(SourceScope.source(5)) == "Pilot"

    def test_unsorted_is_not_for_review(self) -> None:
        with pytest.raises(ScopeNotReviewableError):
            self.resolver.reviewable_sources(SourceScope.unsorted())
        reviewable = self.resolver.reviewable_sources(SourceScope.collection(1))
        assert [s.id for s in reviewable] == [3, 2]


# Added 1 (oldest) .. 4 (newest); the titles and the marks run in other orders.
ORDERED = [
    Source(
        id=1, title="banana", status=SourceStatus.DONE, collection_id=1,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    ),
    Source(
        id=2, title="Apple", status=SourceStatus.NEW, collection_id=1,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    ),
    Source(
        id=3, title="cherry", status=SourceStatus.DONE, collection_id=1,
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    ),
    Source(
        id=4, title="apple", status=SourceStatus.DONE, collection_id=None,
        created_at=datetime(2026, 1, 4, tzinfo=UTC),
    ),
]
PROGRESS = {
    1: DecisionProgress(decided=1, total=2),
    2: DecisionProgress(),
    3: DecisionProgress(decided=0, total=2),
    4: DecisionProgress(decided=0, total=2),
}
LAST_STUDIED = {
    1: datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
    3: datetime(2026, 2, 1, 10, 30, tzinfo=UTC),
}


def ordered_resolver(
    grouping: SourceGrouping, sort: SourceSort,
) -> tuple[SourceScopeResolver, MagicMock]:
    progress = MagicMock()
    progress.of_sources.side_effect = lambda ids: {
        i: SourceProgress(PROGRESS[i], PROGRESS[i].total) for i in ids
    }
    probe = MagicMock()
    probe.of.return_value = TopicGeneration()
    candidates = MagicMock()
    candidates.last_studied.side_effect = lambda ids: {
        i: LAST_STUDIED[i] for i in ids if i in LAST_STUDIED
    }
    resolver = SourceScopeResolver(
        InMemorySourceRepository(list(ORDERED)),
        InMemoryCollectionRepository([Collection(id=1, name="Friends")]),
        SourceOrdering(order_settings(grouping, sort), progress, probe, candidates),
    )
    return resolver, candidates


def ids(resolver: SourceScopeResolver, scope: SourceScope) -> list[int | None]:
    return [s.id for s in resolver.sources(scope)]


@pytest.mark.unit
class TestTheUsersOrder:
    def test_one_order_for_all_and_for_a_collection(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.NONE, SourceSort.NAME)
        assert ids(resolver, SourceScope.all()) == [2, 4, 1, 3]
        assert ids(resolver, SourceScope.collection(1)) == [2, 1, 3]
        assert ids(resolver, SourceScope.unsorted()) == [4]

    def test_review_of_a_collection_follows_the_order(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.STAGE, SourceSort.LAST_STUDIED)
        reviewable = resolver.reviewable_sources(SourceScope.collection(1))
        assert [s.id for s in reviewable] == [1, 2, 3]

    def test_grouped_by_stage_then_sorted_inside(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.STAGE, SourceSort.NAME)
        groups = resolver.groups(SourceScope.all())
        assert [(g.stage, [s.id for s in g.sources]) for g in groups] == [
            (SourceStage.IN_PROGRESS, [1]),
            (SourceStage.PREPARING, [2]),
            (SourceStage.READY, [4, 3]),
        ]
        assert ids(resolver, SourceScope.all()) == [1, 2, 4, 3]

    def test_ungrouped_is_one_group_without_a_stage(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.NONE, SourceSort.ADDED)
        groups = resolver.groups(SourceScope.all())
        assert [(g.stage, [s.id for s in g.sources]) for g in groups] == [(None, [4, 3, 2, 1])]

    def test_marks_are_read_only_for_the_last_studied_sort(self) -> None:
        resolver, candidates = ordered_resolver(SourceGrouping.NONE, SourceSort.NAME)
        resolver.sources(SourceScope.all())
        candidates.last_studied.assert_not_called()

    def test_last_studied_puts_the_never_marked_after_by_date_added(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.NONE, SourceSort.LAST_STUDIED)
        assert ids(resolver, SourceScope.all()) == [3, 1, 4, 2]

    def test_a_source_scope_is_that_source_whatever_the_order(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.STAGE, SourceSort.NAME)
        assert ids(resolver, SourceScope.source(3)) == [3]

    def test_oldest_added_first_ignores_the_users_sort(self) -> None:
        resolver, _ = ordered_resolver(SourceGrouping.NONE, SourceSort.NAME)
        assert [s.id for s in resolver.oldest_added_first(SourceScope.all())] == [1, 2, 3, 4]
