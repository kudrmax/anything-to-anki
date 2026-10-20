from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.domain.value_objects.format import Format
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.video_path_resolver import VideoPathResolver

logger = logging.getLogger(__name__)


class CleanupYoutubeVideoUseCase:
    """Deletes downloaded YouTube video after all media has been extracted."""

    def __init__(
        self,
        source_repo: SourceRepository,
        media_repo: CandidateMediaRepository,
        job_repo: JobRepository,
        video_path_resolver: VideoPathResolver,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._source_repo = source_repo
        self._media_repo = media_repo
        self._job_repo = job_repo
        self._video_path_resolver = video_path_resolver
        self._unit_of_work = unit_of_work

    def execute(self, source_id: int) -> None:
        """The source forgets its video in a write; the file goes after it is committed,
        so none is deleted under the write lock or for a write that was rolled back."""
        with self._unit_of_work.write():
            video = self._forget_video(source_id)
        if video is not None and os.path.exists(video):
            os.remove(video)
            logger.info("Cleaned up YouTube video: %s (source %d)", video, source_id)

    def _forget_video(self, source_id: int) -> str | None:
        """Clears the video of a YouTube source whose media is all extracted; returns the
        file it named."""
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return None
        if source.format is not Format.YOUTUBE:
            return None
        if source.video_path is None:
            return None

        # Don't clean up if media jobs are still active
        if self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.MEDIA}),
        ):
            return None

        all_media = self._media_repo.get_all_by_source_id(source_id)
        if not all_media:
            return None
        if not all(m.screenshot_path is not None for m in all_media):
            return None

        resolved_path = self._video_path_resolver.resolve(source.video_path, source.format)
        self._source_repo.update_video_path(source_id, None)
        return resolved_path
