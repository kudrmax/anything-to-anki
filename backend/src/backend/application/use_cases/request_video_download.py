from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.job import Job
from backend.domain.exceptions import SourceHasNoUrlError, VideoAlreadyDownloadedError
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.exceptions import DomainError
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.value_objects.source_scope import SourceScope

# Why a source of a set has no video to download: no link, or the file is here already.
_SKIPPED = (SourceHasNoUrlError, VideoAlreadyDownloadedError)
_VIDEO_DOWNLOAD = frozenset({JobType.VIDEO_DOWNLOAD})


class RequestVideoDownloadUseCase:
    """Queues the download of the video of every source of a set that has a link and no
    file yet, once each; a source whose download is already queued or running is left as
    is. A set with nothing to download fails with its first source's reason."""

    def __init__(self, scope_resolver: SourceScopeResolver, job_repo: JobRepository) -> None:
        self._scope_resolver = scope_resolver
        self._job_repo = job_repo

    def execute(self, scope: SourceScope) -> int:
        """Returns how many downloads were queued."""
        jobs: list[Job] = []
        skipped: list[DomainError] = []
        for source in self._scope_resolver.reviewable_sources(scope):
            try:
                job = _download(source)
            except _SKIPPED as e:
                skipped.append(e)
                continue
            if not self._job_repo.has_active_jobs_for_source(job.source_id, _VIDEO_DOWNLOAD):
                jobs.append(job)
        if not jobs and skipped:
            raise skipped[0]
        if jobs:
            self._job_repo.enqueue(jobs)
        return len(jobs)


def _download(source: Source) -> Job:
    assert source.id is not None
    if source.source_url is None:
        raise SourceHasNoUrlError(source.id)
    if source.video_path is not None:
        raise VideoAlreadyDownloadedError(source.id)
    return Job.queued(JobType.VIDEO_DOWNLOAD, source.id)
