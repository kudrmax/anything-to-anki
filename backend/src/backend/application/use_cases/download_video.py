from __future__ import annotations

import logging
import os
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.video_downloader import VideoDownloader

logger = logging.getLogger(__name__)


class DownloadVideoUseCase:
    """Downloads video for a YouTube source. Called from worker job."""

    def __init__(
        self,
        source_repo: SourceRepository,
        video_downloader: VideoDownloader,
        videos_dir: str,
    ) -> None:
        self._source_repo = source_repo
        self._video_downloader = video_downloader
        self._videos_dir = videos_dir

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source {source_id} not found")
        if source.source_url is None:
            raise ValueError(f"Source {source_id} has no source_url")
        if source.video_path is not None:
            raise ValueError(f"Source {source_id} video already downloaded")

        os.makedirs(self._videos_dir, exist_ok=True)
        output_path = os.path.join(self._videos_dir, f"{uuid.uuid4()}.mp4")

        self._video_downloader.download(source.source_url, output_path)

        self._source_repo.update_video_path(source_id, output_path)
        logger.info("Downloaded video for source %d → %s", source_id, output_path)
