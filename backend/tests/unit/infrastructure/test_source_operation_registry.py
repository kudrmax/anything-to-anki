import pytest
from backend.application.dto.rebuild_dtos import OperationState, TopicRefreshSummaryDTO
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.infrastructure.api.source_operations import SourceOperationRegistry

SOURCE = 1


@pytest.mark.unit
class TestSourceOperationRegistry:
    def test_a_started_operation_says_what_runs(self) -> None:
        registry = SourceOperationRegistry()
        started = registry.started(SOURCE, SourceOperationKind.PREVIEW)
        assert started.state is OperationState.RUNNING
        assert started.caption == "Checking what a rebuild changes…"

    def test_a_failed_operation_keeps_its_error(self) -> None:
        registry = SourceOperationRegistry()
        started = registry.started(SOURCE, SourceOperationKind.REBUILD)

        registry.failed(SOURCE, started.operation_id, "parser crashed")

        last = registry.last(SOURCE)
        assert last is not None
        assert (last.state, last.error, last.kind) == (
            OperationState.ERROR, "parser crashed", SourceOperationKind.REBUILD,
        )
        assert last.summary is None

    def test_a_finished_operation_keeps_its_result(self) -> None:
        registry = SourceOperationRegistry()
        started = registry.started(SOURCE, SourceOperationKind.REFRESH)
        refreshed = TopicRefreshSummaryDTO(words_added=1, phrases_added=2)

        registry.finished(SOURCE, started.operation_id, refresh=refreshed)

        last = registry.last(SOURCE)
        assert last is not None
        assert (last.state, last.refresh) == (OperationState.DONE, refreshed)

    def test_an_older_operation_does_not_overwrite_a_newer_one(self) -> None:
        registry = SourceOperationRegistry()
        older = registry.started(SOURCE, SourceOperationKind.PREVIEW)
        newer = registry.started(SOURCE, SourceOperationKind.REBUILD)

        registry.failed(SOURCE, older.operation_id, "late")

        assert registry.last(SOURCE) == newer

    def test_a_source_without_operations_has_none(self) -> None:
        assert SourceOperationRegistry().last(SOURCE) is None
