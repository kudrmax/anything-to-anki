from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.rebuild_dtos import (
    RebuildCountsDTO,
    RebuildPreviewDTO,
    RebuildSummaryDTO,
    TopicRefreshSummaryDTO,
)
from backend.application.use_cases.scope_operation import ScopeOperationUseCase
from backend.application.utils.long_operation_runner import OperationResult
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

from tests.source_order_support import added_order
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository

if TYPE_CHECKING:
    from collections.abc import Callable

PILOT, FINALE, NEW, TOPIC = 1, 2, 3, 4
UPDATE = RebuildMode.UPDATE
RECUT = RebuildMode.RECUT
_CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def _counts(added: int, *, nothing: bool = False) -> RebuildCountsDTO:
    return RebuildCountsDTO(
        words_added=added, words_removed=1, cards_lost_generation=0, cards_moved=2,
        cards_recut=0, cards_recut_lost_text_generation=0, cards_became_ready=0,
        cards_left_ready=0, nothing_to_update=nothing,
    )


@pytest.mark.unit
class TestScopeOperationUseCase:
    def setup_method(self) -> None:
        self.sources = [
            Source(id=PILOT, status=SourceStatus.DONE, created_at=_CREATED),
            Source(id=FINALE, status=SourceStatus.DONE, created_at=_CREATED),
            Source(id=NEW, status=SourceStatus.NEW, created_at=_CREATED),
            Source(
                id=TOPIC, status=SourceStatus.DONE, role=SourceRole.TOPIC,
                topic_query="salary talk", created_at=_CREATED,
            ),
        ]
        self.held: dict[int, SourceOperationKind] = {}
        self.lock = MagicMock()
        self.lock.held.side_effect = self.held.get
        self.rebuild = MagicMock()
        self.rebuild.start.side_effect = self._start
        self.refresh = MagicMock()
        self.refresh.start.side_effect = lambda source_id: self._start(
            source_id, None, SourceOperationKind.REFRESH,
        )
        self.unit_of_work = MagicMock()
        self.use_case = ScopeOperationUseCase(
            scope_resolver=SourceScopeResolver(
                InMemorySourceRepository(self.sources), InMemoryCollectionRepository(),
                added_order(),
            ),
            rebuild_source=self.rebuild,
            refresh_topic=self.refresh,
            lock=self.lock,
            unit_of_work=self.unit_of_work,
        )

    def _start(
        self, source_id: int, mode: RebuildMode | None, kind: SourceOperationKind,
    ) -> None:
        if source_id in self.held:
            raise SourceOperationBusyError(source_id, self.held[source_id])

    def _rebuilt(
        self, failing: frozenset[int] = frozenset(),
    ) -> list[int]:
        """The rebuild of the use case runs: the sources it was given, in order."""
        given: list[int] = []

        def rebuild(
            targets: Callable[[], list[int]], mode: RebuildMode,
        ) -> OperationResult[RebuildSummaryDTO]:
            given.extend(targets())
            return OperationResult(
                [
                    RebuildSummaryDTO(mode=mode, counts=_counts(t))
                    for t in given if t not in failing
                ],
                [(t, RuntimeError("analysis broke")) for t in given if t in failing],
            )

        self.rebuild.rebuild.side_effect = rebuild
        return given

    def test_an_update_runs_every_source_offering_it_in_the_set_order_and_sums(self) -> None:
        given = self._rebuilt()

        summary = self.use_case.rebuild(SourceScope.all(), UPDATE)

        assert given == [PILOT, FINALE, TOPIC]
        assert summary is not None
        assert summary.mode is UPDATE
        assert summary.counts.words_added == PILOT + FINALE + TOPIC
        assert summary.counts.words_removed == 3
        assert summary.counts.nothing_to_update is False
        assert (summary.skipped, summary.failed) == (0, 0)

    def test_a_recut_skips_the_sources_without_text_of_their_own(self) -> None:
        given = self._rebuilt()

        summary = self.use_case.rebuild(SourceScope.all(), RECUT)

        assert given == [PILOT, FINALE]
        assert summary is not None
        assert summary.mode is RECUT

    def test_a_source_is_a_set_of_one(self) -> None:
        given = self._rebuilt()

        summary = self.use_case.rebuild(SourceScope.source(PILOT), UPDATE)

        assert given == [PILOT]
        assert summary == RebuildSummaryDTO(mode=UPDATE, counts=_counts(PILOT))

    def test_a_failed_source_is_counted_and_the_rest_go_on(self) -> None:
        self._rebuilt(failing=frozenset({PILOT}))

        summary = self.use_case.rebuild(SourceScope.all(), UPDATE)

        assert summary is not None
        assert summary.counts.words_added == FINALE + TOPIC
        assert (summary.skipped, summary.failed) == (0, 1)

    def test_the_operation_fails_when_every_source_failed(self) -> None:
        self._rebuilt(failing=frozenset({PILOT, FINALE, TOPIC}))

        with pytest.raises(RuntimeError, match="analysis broke"):
            self.use_case.rebuild(SourceScope.all(), UPDATE)

    def test_a_cancelled_rebuild_has_no_summary(self) -> None:
        self.rebuild.rebuild.return_value = None

        assert self.use_case.rebuild(SourceScope.all(), UPDATE) is None

    def test_a_preview_sums_the_sources_offering_the_mode(self) -> None:
        self.rebuild.run_preview.side_effect = lambda source_id, mode: RebuildPreviewDTO(
            mode=mode, counts=_counts(1, nothing=source_id != PILOT),
        )

        preview = self.use_case.preview(SourceScope.all(), RECUT)

        assert preview.mode is RECUT
        assert preview.counts.words_added == 2
        assert preview.counts.nothing_to_update is False
        self.rebuild.start.assert_any_call(PILOT, RECUT, SourceOperationKind.PREVIEW)
        assert [c.args for c in self.rebuild.run_preview.call_args_list] == [
            (PILOT, RECUT), (FINALE, RECUT),
        ]

    def test_a_refresh_runs_the_topics_of_the_set(self) -> None:
        given: list[int] = []

        def refresh(targets: Callable[[], list[int]]) -> OperationResult[TopicRefreshSummaryDTO]:
            given.extend(targets())
            return OperationResult([TopicRefreshSummaryDTO(words_added=2, phrases_added=5)], [])

        self.refresh.refresh.side_effect = refresh

        refreshed = self.use_case.refresh(SourceScope.all())

        assert given == [TOPIC]
        assert refreshed is not None
        assert (refreshed.words_added, refreshed.phrases_added) == (2, 5)

    def test_a_set_without_a_source_offering_the_operation_cannot_start(self) -> None:
        with pytest.raises(RebuildNotSupportedError):
            self.use_case.check(SourceScope.source(NEW), SourceOperationKind.UPDATE)
        with pytest.raises(RefreshNotSupportedError):
            self.use_case.check(SourceScope.source(PILOT), SourceOperationKind.REFRESH)

    def test_a_topic_alone_cannot_be_recut(self) -> None:
        with pytest.raises(RebuildNotSupportedError):
            self.use_case.check(SourceScope.source(TOPIC), SourceOperationKind.RECUT)
        self.use_case.check(SourceScope.source(TOPIC), SourceOperationKind.UPDATE)

    def test_a_set_whose_every_offering_source_is_busy_cannot_start(self) -> None:
        self.held[PILOT] = SourceOperationKind.UPDATE
        self.held[FINALE] = SourceOperationKind.PROCESS
        self.use_case.check(SourceScope.all(), SourceOperationKind.UPDATE)

        self.held[TOPIC] = SourceOperationKind.REFRESH
        with pytest.raises(SourceOperationBusyError):
            self.use_case.check(SourceScope.all(), SourceOperationKind.UPDATE)

    def test_a_missing_source_is_not_found(self) -> None:
        with pytest.raises(SourceNotFoundError):
            self.use_case.check(SourceScope.source(99), SourceOperationKind.UPDATE)
