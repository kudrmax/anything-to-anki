from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.download_video import DownloadVideoUseCase
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_youtube_source(source_url: str = "https://youtube.com/watch?v=abc") -> Source:
    return Source(
        raw_text="1\n00:00:01,000 --> 00:00:02,000\nHello\n",
        status=SourceStatus.DONE,
        input_method=InputMethod.YOUTUBE_URL,
        content_type=ContentType.VIDEO,
        source_url=source_url,
        id=42,
    )


class TestDownloadVideo:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.video_downloader = MagicMock()
        self.videos_dir = "/data/videos"
        self.use_case = DownloadVideoUseCase(
            source_repo=self.source_repo,
            video_downloader=self.video_downloader,
            videos_dir=self.videos_dir,
        )

    def test_downloads_and_sets_video_path(self) -> None:
        source = _make_youtube_source()
        self.source_repo.get_by_id.return_value = source
        with patch("backend.application.use_cases.download_video.os.makedirs"):
            self.use_case.execute(42)
        self.video_downloader.download.assert_called_once()
        call_args = self.video_downloader.download.call_args
        assert call_args[0][0] == "https://youtube.com/watch?v=abc"
        assert call_args[0][1].startswith("/data/videos/")
        assert call_args[0][1].endswith(".mp4")

    def test_raises_if_no_source_url(self) -> None:
        source = _make_youtube_source()
        source.source_url = None
        self.source_repo.get_by_id.return_value = source
        with pytest.raises(ValueError, match="source_url"):
            self.use_case.execute(42)

    def test_raises_if_video_already_downloaded(self) -> None:
        source = _make_youtube_source()
        source.video_path = "/data/videos/existing.mp4"
        self.source_repo.get_by_id.return_value = source
        with pytest.raises(ValueError, match="already downloaded"):
            self.use_case.execute(42)
