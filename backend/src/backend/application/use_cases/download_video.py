from __future__ import annotations

import logging
import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_downloader import VideoDownloader
    from backend.domain.ports.video_path_resolver import VideoPathResolver

logger = logging.getLogger(__name__)


class DownloadVideoUseCase:
    """Downloads video for a YouTube source. Called from worker job."""

    def __init__(
        self,
        source_repo: SourceRepository,
        video_downloader: VideoDownloader,
        video_path_resolver: VideoPathResolver,
    ) -> None:
        self._source_repo = source_repo
        self._video_downloader = video_downloader
        self._video_path_resolver = video_path_resolver

    def execute(self, source_id: int) -> None:
        from backend.domain.value_objects.input_method import InputMethod

        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source {source_id} not found")
        if source.source_url is None:
            raise ValueError(f"Source {source_id} has no source_url")
        if source.video_path is not None:
            raise ValueError(f"Source {source_id} video already downloaded")

        filename = f"{uuid.uuid4()}.mp4"
        absolute_path = self._video_path_resolver.resolve(filename, InputMethod.YOUTUBE_URL)
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)

        self._video_downloader.download(source.source_url, absolute_path)

        self._source_repo.update_video_path(source_id, filename)
        logger.info("Downloaded video for source %d → %s", source_id, filename)
