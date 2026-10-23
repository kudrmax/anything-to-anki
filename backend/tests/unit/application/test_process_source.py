"""Whether a source may be processed, and a processing whose source fails: its error is on
the source, written with the rest of the operation."""
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.process_source import ERROR_DETAIL_LENGTH, ProcessSourceUseCase
from backend.application.utils.long_operation_runner import OperationResult
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    SourceAlreadyProcessedError,
    SourceNotFoundError,
    SourceOperationBusyError,
    TopicTargetsMissingError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus


def _source(status: SourceStatus, role: SourceRole = SourceRole.CONTENT) -> Source:
    return Source(id=1, status=status, format=Format.PLAIN, kind=Kind.TEXT, role=role)


class _Runner:
    """Runs the work as the real runner does with nothing else: each target prepared, then
    applied, then the failures told."""

    def run(self, work: object) -> OperationResult[None]:
        targets = work.targets()  # type: ignore[attr-defined]
        prepared, failures = [], []
        for source_id in targets:
            try:
                prepared.append(work.prepare(source_id, lambda _part: None))  # type: ignore[attr-defined]
            except Exception as e:
                failures.append((source_id, e))
        for item in prepared:
            work.apply(item)  # type: ignore[attr-defined]
        for source_id, error in failures:
            work.failed(source_id, error)  # type: ignore[attr-defined]
        return OperationResult([None] * len(prepared), failures)


@pytest.mark.unit
class TestProcessSource:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.lock = MagicMock()
        self.lock.held.return_value = None
        self.rebuilder = MagicMock()
        self.collector = MagicMock()
        self.use_case = ProcessSourceUseCase(
            source_repo=self.source_repo,
            collected_phrases=MagicMock(),
            lock=self.lock,
            rebuilder=self.rebuilder,
            runner=_Runner(),  # type: ignore[arg-type]
            topic_phrase_collector=self.collector,
        )

    def test_a_new_source_may_be_processed(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW)
        self.use_case.check(1)

    def test_a_missing_source_may_not(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.check(999)

    def test_a_processed_source_may_not(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        with pytest.raises(SourceAlreadyProcessedError):
            self.use_case.check(1)

    def test_a_failed_source_may_be_processed_again(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.ERROR)
        self.use_case.check(1)

    def test_a_source_in_a_preview_may_not(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW)
        self.lock.held.return_value = SourceOperationKind.PREVIEW
        with pytest.raises(SourceOperationBusyError):
            self.use_case.check(1)

    def test_a_topic_without_targets_may_not(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW, SourceRole.TOPIC)
        self.collector.has_targets.return_value = False
        with pytest.raises(TopicTargetsMissingError):
            self.use_case.check(1)

    def test_a_source_that_fails_shows_the_tail_of_its_error(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW)
        self.rebuilder.analyse.side_effect = RuntimeError("x" * (2 * ERROR_DETAIL_LENGTH))

        result = self.use_case.run([1])

        assert result is not None
        assert result.failed == 1
        [call] = self.source_repo.update_status.call_args_list
        source_id, status = call.args
        detail = call.kwargs["error_message"]
        assert (source_id, status) == (1, SourceStatus.ERROR)
        assert len(detail) == ERROR_DETAIL_LENGTH
        assert detail.endswith("x\n")
