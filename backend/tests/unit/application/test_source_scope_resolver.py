from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    CollectionNotFoundError,
    ScopeNotReviewableError,
    SourceNotFoundError,
)
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

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
        )
        assert resolver.title(SourceScope.source(5)) == "Pilot"

    def test_unsorted_is_not_for_review(self) -> None:
        with pytest.raises(ScopeNotReviewableError):
            self.resolver.reviewable_sources(SourceScope.unsorted())
        reviewable = self.resolver.reviewable_sources(SourceScope.collection(1))
        assert [s.id for s in reviewable] == [3, 2]
