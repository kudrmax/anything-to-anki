from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    GenerationAlreadyRunningError,
    SourceNotFoundError,
    SourceNotTopicError,
    TopicTargetsAlreadyGeneratedError,
)
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository

logger = logging.getLogger(__name__)

_TOPIC_JOB_TYPES = frozenset({JobType.TOPIC_TARGETS})


class EnqueueTopicGenerationUseCase:
    """Queues the AI step of a topic source: turning its request into targets."""

    def __init__(
        self,
        source_repo: SourceRepository,
        topic_target_repo: TopicTargetRepository,
        job_repo: JobRepository,
    ) -> None:
        self._source_repo = source_repo
        self._topic_target_repo = topic_target_repo
        self._job_repo = job_repo

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.content_type != ContentType.TOPIC:
            raise SourceNotTopicError(source_id)
        if self._topic_target_repo.has_targets(source_id):
            raise TopicTargetsAlreadyGeneratedError(source_id)
        if self._job_repo.has_active_jobs_for_source(source_id, _TOPIC_JOB_TYPES):
            raise GenerationAlreadyRunningError()

        self._job_repo.enqueue([Job.queued(JobType.TOPIC_TARGETS, source_id)])
        logger.info("enqueue_topic_generation: queued (source_id=%d)", source_id)
