from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.domain.exceptions import SubtitlesNotAvailableError
from backend.domain.value_objects.input_method import InputMethod
from backend.infrastructure.adapters.ytdlp_subtitle_fetcher import YtDlpSubtitleFetcher


class TestYtDlpSubtitleFetcherCanHandle:
    def setup_method(self) -> None:
        self.fetcher = YtDlpSubtitleFetcher()

    def test_youtube_com_url(self) -> None:
        assert self.fetcher.can_handle("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtu_be_short_url(self) -> None:
        assert self.fetcher.can_handle("https://youtu.be/dQw4w9WgXcQ")

    def test_youtube_with_playlist(self) -> None:
        assert self.fetcher.can_handle("https://www.youtube.com/watch?v=abc&list=xyz")

    def test_non_youtube_url(self) -> None:
        assert not self.fetcher.can_handle("https://genius.com/some-lyrics")

    def test_random_url(self) -> None:
        assert not self.fetcher.can_handle("https://example.com")

    def test_empty_string(self) -> None:
        assert not self.fetcher.can_handle("")


class TestYtDlpSubtitleFetcherFetch:
    def setup_method(self) -> None:
        self.fetcher = YtDlpSubtitleFetcher()

    def test_fetch_happy_path(self) -> None:
        """Mock yt-dlp, write SRT file in temp dir, verify result."""
        srt_content = "1\n00:00:01,000 --> 00:00:02,000\nHello world\n"

        with tempfile.TemporaryDirectory() as real_tmpdir:
            # Pre-write the SRT file that yt-dlp would create
            srt_path = Path(real_tmpdir) / "sub.en.srt"
            srt_path.write_text(srt_content)

            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = {"title": "Test Video"}
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch(
                    "tempfile.TemporaryDirectory"
                ) as mock_tmpdir_cls:
                    mock_ctx = MagicMock()
                    mock_ctx.__enter__ = MagicMock(return_value=real_tmpdir)
                    mock_ctx.__exit__ = MagicMock(return_value=False)
                    mock_tmpdir_cls.return_value = mock_ctx

                    result = self.fetcher.fetch_subtitles(
                        "https://youtube.com/watch?v=abc"
                    )

        assert result.srt_text == srt_content
        assert result.title == "Test Video"
        assert result.input_method == InputMethod.YOUTUBE_URL

    def test_fetch_no_srt_raises(self) -> None:
        """No SRT file created → SubtitlesNotAvailableError."""
        with tempfile.TemporaryDirectory() as real_tmpdir:
            mock_ydl = MagicMock()
            mock_ydl.extract_info.return_value = {"title": "No Subs"}
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)

            with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
                with patch(
                    "tempfile.TemporaryDirectory"
                ) as mock_tmpdir_cls:
                    mock_ctx = MagicMock()
                    mock_ctx.__enter__ = MagicMock(return_value=real_tmpdir)
                    mock_ctx.__exit__ = MagicMock(return_value=False)
                    mock_tmpdir_cls.return_value = mock_ctx

                    with pytest.raises(SubtitlesNotAvailableError):
                        self.fetcher.fetch_subtitles(
                            "https://youtube.com/watch?v=abc"
                        )

    def test_fetch_extract_info_returns_none(self) -> None:
        """extract_info returns None → SubtitlesNotAvailableError."""
        mock_ydl = MagicMock()
        mock_ydl.extract_info.return_value = None
        mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl.__exit__ = MagicMock(return_value=False)

        with patch("yt_dlp.YoutubeDL", return_value=mock_ydl):
            with pytest.raises(SubtitlesNotAvailableError):
                self.fetcher.fetch_subtitles("https://youtube.com/watch?v=abc")
