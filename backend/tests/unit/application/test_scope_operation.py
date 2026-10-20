from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.dto.rebuild_dtos import (
    RebuildCountsDTO,
    RebuildPreviewDTO,
    RebuildSummaryDTO,
    TopicRefreshSummaryDTO,
)
from backend.application.use_cases.scope_operation import ScopeOperationUseCase
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    RefreshNotSupportedError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository

PILOT, FINALE, NEW, TOPIC = 1, 2, 3, 4
_CREATED = datetime(2026, 1, 1, tzinfo=UTC)


def _counts(added: int, *, nothing: bool = False) -> RebuildCountsDTO:
    return RebuildCountsDTO(
        words_added=added, words_removed=1, cards_new_phrase=0, cards_text_reset=0,
        cards_without_generation=2, nothing_to_update=nothing,
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
            source_id, SourceOperationKind.REFRESH,
        )
        self.unit_of_work = MagicMock()
        self.use_case = ScopeOperationUseCase(
            scope_resolver=SourceScopeResolver(
                InMemorySourceRepository(self.sources), InMemoryCollectionRepository(),
            ),
            rebuild_source=self.rebuild,
            refresh_topic=self.refresh,
            lock=self.lock,
            unit_of_work=self.unit_of_work,
        )

    def _start(self, source_id: int, kind: SourceOperationKind) -> None:
        if source_id in self.held:
            raise SourceOperationBusyError(source_id, self.held[source_id])

    def test_a_rebuild_runs_every_source_offering_it_in_the_set_order_and_sums(self) -> None:
        self.rebuild.run.side_effect = lambda source_id, include_open: RebuildSummaryDTO(
            include_open=include_open and source_id == PILOT, counts=_counts(source_id),
        )

        summary = self.use_case.rebuild(SourceScope.all(), include_open=True)

        assert [c.args[0] for c in self.rebuild.run.call_args_list] == [PILOT, FINALE, TOPIC]
        assert summary.include_open is True
        assert summary.counts.words_added == PILOT + FINALE + TOPIC
        assert summary.counts.words_removed == 3
        assert summary.counts.nothing_to_update is False
        assert (summary.skipped, summary.failed) == (0, 0)

    def test_a_source_is_a_set_of_one(self) -> None:
        self.rebuild.run.return_value = RebuildSummaryDTO(
            include_open=False, counts=_counts(5),
        )

        summary = self.use_case.rebuild(SourceScope.source(PILOT), include_open=False)

        self.rebuild.start.assert_called_once_with(PILOT, SourceOperationKind.REBUILD)
        assert summary == RebuildSummaryDTO(include_open=False, counts=_counts(5))

    def test_a_source_busy_at_its_turn_is_skipped_and_counted(self) -> None:
        self.held[FINALE] = SourceOperationKind.PROCESS
        self.rebuild.run.return_value = RebuildSummaryDTO(
            include_open=False, counts=_counts(1),
        )

        summary = self.use_case.rebuild(SourceScope.all(), include_open=False)

        assert [c.args[0] for c in self.rebuild.run.call_args_list] == [PILOT, TOPIC]
        assert (summary.skipped, summary.failed) == (1, 0)

    def test_a_failed_source_is_counted_and_the_rest_go_on(self) -> None:
        def run(source_id: int, include_open: bool) -> RebuildSummaryDTO:
            if source_id == PILOT:
                raise RuntimeError("analysis broke")
            return RebuildSummaryDTO(include_open=include_open, counts=_counts(1))

        self.rebuild.run.side_effect = run

        summary = self.use_case.rebuild(SourceScope.all(), include_open=False)

        assert summary.counts.words_added == 2
        assert (summary.skipped, summary.failed) == (0, 1)

    def test_the_operation_fails_when_every_source_failed(self) -> None:
        self.rebuild.run.side_effect = RuntimeError("analysis broke")

        with pytest.raises(RuntimeError, match="analysis broke"):
            self.use_case.rebuild(SourceScope.all(), include_open=False)

    def test_a_preview_has_the_switch_if_any_source_has_it(self) -> None:
        self.rebuild.run_preview.side_effect = lambda source_id: RebuildPreviewDTO(
            without_open=_counts(1, nothing=True),
            with_open=_counts(10) if source_id == PILOT else None,
        )

        preview = self.use_case.preview(SourceScope.all())

        assert preview.without_open.words_added == 3
        assert preview.without_open.nothing_to_update is True
        assert preview.with_open is not None
        assert preview.with_open.words_added == 10 + 1 + 1
        assert preview.with_open.nothing_to_update is False
        self.rebuild.start.assert_any_call(PILOT, SourceOperationKind.PREVIEW)

    def test_a_preview_without_any_switch_has_none(self) -> None:
        self.rebuild.run_preview.return_value = RebuildPreviewDTO(
            without_open=_counts(1), with_open=None,
        )

        assert self.use_case.preview(SourceScope.all()).with_open is None

    def test_a_refresh_runs_the_topics_of_the_set(self) -> None:
        self.refresh.run.return_value = TopicRefreshSummaryDTO(words_added=2, phrases_added=5)

        refresh = self.use_case.refresh(SourceScope.all())

        self.refresh.run.assert_called_once_with(TOPIC)
        assert (refresh.words_added, refresh.phrases_added) == (2, 5)

    def test_a_set_without_a_source_offering_the_operation_cannot_start(self) -> None:
        with pytest.raises(RebuildNotSupportedError):
            self.use_case.check(SourceScope.source(NEW), SourceOperationKind.REBUILD)
        with pytest.raises(RefreshNotSupportedError):
            self.use_case.check(SourceScope.source(PILOT), SourceOperationKind.REFRESH)

    def test_a_set_whose_every_offering_source_is_busy_cannot_start(self) -> None:
        self.held[PILOT] = SourceOperationKind.REBUILD
        self.held[FINALE] = SourceOperationKind.PROCESS
        self.use_case.check(SourceScope.all(), SourceOperationKind.REBUILD)

        self.held[TOPIC] = SourceOperationKind.REFRESH
        with pytest.raises(SourceOperationBusyError):
            self.use_case.check(SourceScope.all(), SourceOperationKind.REBUILD)

    def test_a_missing_source_is_not_found(self) -> None:
        with pytest.raises(SourceNotFoundError):
            self.use_case.check(SourceScope.source(99), SourceOperationKind.REBUILD)
