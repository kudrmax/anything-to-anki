from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.process_source import ProcessSourceUseCase
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


@pytest.mark.unit
class TestProcessSourceStart:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.lock = MagicMock()
        self.lock.acquire.return_value = True
        self.rebuilder = MagicMock()
        self.collector = MagicMock()
        self.use_case = ProcessSourceUseCase(
            source_repo=self.source_repo,
            collected_phrases=MagicMock(),
            lock=self.lock,
            unit_of_work=MagicMock(),
            rebuilder=self.rebuilder,
            topic_phrase_collector=self.collector,
        )

    def test_start_takes_the_source_and_leaves_its_status(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW)

        self.use_case.start(1)

        self.lock.acquire.assert_called_once_with(1, SourceOperationKind.PROCESS)
        self.source_repo.update_status.assert_not_called()

    def test_start_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.start(999)
        self.lock.acquire.assert_not_called()

    def test_start_already_done(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        with pytest.raises(SourceAlreadyProcessedError):
            self.use_case.start(1)
        self.lock.acquire.assert_not_called()

    def test_start_allows_error_retry(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.ERROR)
        self.use_case.start(1)
        self.lock.acquire.assert_called_once()

    def test_a_busy_source_does_not_start(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW)
        self.lock.acquire.return_value = False
        with pytest.raises(SourceOperationBusyError):
            self.use_case.start(1)
        self.source_repo.update_status.assert_not_called()

    def test_a_topic_without_targets_does_not_start(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.NEW, SourceRole.TOPIC)
        self.collector.has_targets.return_value = False
        with pytest.raises(TopicTargetsMissingError):
            self.use_case.start(1)
        self.lock.acquire.assert_not_called()

    def test_execute_of_a_missing_source_frees_it(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)
        self.lock.release.assert_called_once_with(999)
        self.rebuilder.analyse.assert_not_called()
