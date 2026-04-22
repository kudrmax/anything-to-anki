from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_type import JobType

if TYPE_CHECKING:
    from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
    from backend.domain.ports.job_repository import JobRepository
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class CleanupYoutubeVideoUseCase:
    """Deletes downloaded YouTube video after all media has been extracted."""

    def __init__(
        self,
        source_repo: SourceRepository,
        media_repo: CandidateMediaRepository,
        job_repo: JobRepository,
    ) -> None:
        self._source_repo = source_repo
        self._media_repo = media_repo
        self._job_repo = job_repo

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            return
        if source.input_method != InputMethod.YOUTUBE_URL:
            return
        if source.video_path is None:
            return

        # Don't clean up if media jobs are still active
        if self._job_repo.has_active_jobs_for_source(
            source_id, frozenset({JobType.MEDIA}),
        ):
            return

        all_media = self._media_repo.get_all_by_source_id(source_id)
        if not all_media:
            return
        if not all(m.screenshot_path is not None for m in all_media):
            return

        video_path = source.video_path
        if os.path.exists(video_path):
            os.remove(video_path)
            logger.info("Cleaned up YouTube video: %s (source %d)", video_path, source_id)

        self._source_repo.update_video_path(source_id, None)
