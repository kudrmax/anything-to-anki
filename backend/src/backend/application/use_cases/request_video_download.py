from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import (
    SourceHasNoUrlError,
    SourceNotFoundError,
    VideoAlreadyDownloadedError,
)
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository


class RequestVideoDownloadUseCase:
    """Queues the download of a URL source's video, once."""

    def __init__(self, source_repo: SourceRepository, job_repo: JobRepository) -> None:
        self._source_repo = source_repo
        self._job_repo = job_repo

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if source.source_url is None:
            raise SourceHasNoUrlError(source_id)
        if source.video_path is not None:
            raise VideoAlreadyDownloadedError(source_id)
        self._job_repo.enqueue([Job.queued(JobType.VIDEO_DOWNLOAD, source_id)])
