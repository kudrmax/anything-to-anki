from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.adapters.ytdlp_video_downloader import YtDlpVideoDownloader


class TestYtDlpVideoDownloaderInit:
    def test_can_instantiate(self) -> None:
        downloader = YtDlpVideoDownloader()
        assert downloader is not None


class TestYtDlpVideoDownloader:
    def setup_method(self) -> None:
        self.downloader = YtDlpVideoDownloader()

    def test_download_calls_ytdlp_correctly(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl) as mock_ytdlp_cls:
            self.downloader.download("https://youtube.com/watch?v=abc", "/tmp/out.mp4")

        mock_ytdlp_cls.assert_called_once()
        opts = mock_ytdlp_cls.call_args[0][0]
        assert opts["outtmpl"] == "/tmp/out.mp4"
        assert "1080" in opts["format"]
        mock_ydl.download.assert_called_once_with(["https://youtube.com/watch?v=abc"])

    def test_download_propagates_error(self) -> None:
        mock_ydl = MagicMock()
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.download.side_effect = Exception("network error")

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(Exception, match="network error"):
                self.downloader.download(
                    "https://youtube.com/watch?v=abc", "/tmp/out.mp4"
                )
