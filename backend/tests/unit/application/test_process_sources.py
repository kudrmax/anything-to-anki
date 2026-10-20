from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.process_sources import ProcessSourcesUseCase
from backend.application.utils.source_ordering import SourceOrdering
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.application.utils.topic_generation import TopicGeneration
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceAlreadyProcessedError
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_order import SourceGrouping, SourceSort
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

from tests.source_order_support import order_settings
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository

# Titles run against the date added: the user's sort by name must not reach processing.
TITLES = {1: "d", 2: "c", 3: "b", 4: "a"}


def source(source_id: int, status: SourceStatus, collection_id: int | None) -> Source:
    return Source(
        id=source_id,
        title=TITLES[source_id],
        status=status,
        collection_id=collection_id,
        created_at=datetime(2026, 1, source_id, tzinfo=UTC),
    )


@pytest.mark.unit
class TestProcessSources:
    def setup_method(self) -> None:
        resolver = SourceScopeResolver(
            InMemorySourceRepository([
                source(1, SourceStatus.NEW, 1),
                source(2, SourceStatus.ERROR, 1),
                source(3, SourceStatus.DONE, 1),
                source(4, SourceStatus.NEW, None),
            ]),
            InMemoryCollectionRepository([Collection(id=1, name="IELTS")]),
            SourceOrdering(
                order_settings(SourceGrouping.NONE, SourceSort.NAME),
                MagicMock(), MagicMock(), MagicMock(),
            ),
        )
        self.resolver = resolver
        probe = MagicMock()
        probe.of.return_value = TopicGeneration()
        self.process = MagicMock()
        self.lock = MagicMock()
        self.lock.operations.return_value = {}
        self.use_case = ProcessSourcesUseCase(
            resolver, probe, self.process, self.lock, MagicMock(),
        )

    def test_the_users_sort_does_not_change_the_processing_order(self) -> None:
        assert [s.id for s in self.resolver.sources(SourceScope.all())] == [4, 3, 2, 1]
        assert self.use_case.pending_in(SourceScope.all()) == [1, 2, 4]

    def test_pending_only_in_scope_oldest_first(self) -> None:
        assert self.use_case.pending_in(SourceScope.collection(1)) == [1, 2]
        assert self.use_case.pending_in(SourceScope.all()) == [1, 2, 4]

    def test_a_source_held_by_an_operation_is_not_pending(self) -> None:
        self.lock.operations.return_value = {1: HeldOperation(SourceOperationKind.PROCESS)}
        assert self.use_case.pending_in(SourceScope.all()) == [2, 4]

    def test_start_skips_sources_that_cannot_start(self) -> None:
        self.process.take.side_effect = [SourceAlreadyProcessedError(1), None]
        result = self.use_case.start([1, 2])
        assert result.started == [2]
        assert result.skipped == [1]
