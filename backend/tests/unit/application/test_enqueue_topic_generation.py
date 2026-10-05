from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_topic_generation import (
    EnqueueTopicGenerationUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    GenerationAlreadyRunningError,
    SourceNotFoundError,
    SourceNotTopicError,
    TopicTargetsAlreadyGeneratedError,
)
from backend.domain.value_objects.content_type import resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit

SOURCE_ID = 7


def _source(input_method: InputMethod = InputMethod.TOPIC_QUERY) -> Source:
    return Source(
        id=SOURCE_ID,
        raw_text="negotiating a salary",
        status=SourceStatus.NEW,
        input_method=input_method,
        content_type=resolve_content_type(input_method),
    )


class TestEnqueueTopicGeneration:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = _source()
        self.topic_target_repo = MagicMock()
        self.topic_target_repo.has_targets.return_value = False
        self.job_repo = MagicMock()
        self.job_repo.has_active_jobs_for_source.return_value = False
        self.use_case = EnqueueTopicGenerationUseCase(
            source_repo=self.source_repo,
            topic_target_repo=self.topic_target_repo,
            job_repo=self.job_repo,
        )

    def test_queues_one_source_level_job(self) -> None:
        self.use_case.execute(SOURCE_ID)

        (jobs,), _ = self.job_repo.enqueue.call_args
        assert len(jobs) == 1
        assert jobs[0].job_type == JobType.TOPIC_TARGETS
        assert jobs[0].source_id == SOURCE_ID
        assert jobs[0].candidate_id is None
        assert jobs[0].status == JobStatus.QUEUED

    def test_missing_source_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(SOURCE_ID)

    def test_regular_source_is_rejected(self) -> None:
        self.source_repo.get_by_id.return_value = _source(InputMethod.TEXT_PASTED)
        with pytest.raises(SourceNotTopicError):
            self.use_case.execute(SOURCE_ID)
        self.job_repo.enqueue.assert_not_called()

    def test_topic_with_targets_is_rejected(self) -> None:
        self.topic_target_repo.has_targets.return_value = True
        with pytest.raises(TopicTargetsAlreadyGeneratedError):
            self.use_case.execute(SOURCE_ID)
        self.job_repo.enqueue.assert_not_called()

    def test_second_job_is_not_queued_while_one_is_active(self) -> None:
        self.job_repo.has_active_jobs_for_source.return_value = True
        with pytest.raises(GenerationAlreadyRunningError):
            self.use_case.execute(SOURCE_ID)
        self.job_repo.enqueue.assert_not_called()
