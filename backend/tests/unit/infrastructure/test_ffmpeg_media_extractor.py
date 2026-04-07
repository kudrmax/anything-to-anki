# backend/tests/unit/infrastructure/test_ffmpeg_media_extractor.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.adapters.ffmpeg_media_extractor import FfmpegMediaExtractor


@pytest.mark.unit
class TestFfmpegMediaExtractorScreenshot:
    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_screenshot_uses_webp_with_scale_and_quality(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        extractor = FfmpegMediaExtractor()

        extractor.extract_screenshot("/videos/movie.mkv", 5000, "/media/1_screenshot.webp")

        args = mock_run.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "-ss" in args
        assert "5.0" in args
        assert "-i" in args
        assert "/videos/movie.mkv" in args
        assert "-vframes" in args
        assert "-vf" in args
        # scale expression keeps aspect ratio, max 640 wide, even height
        vf_idx = args.index("-vf")
        assert "scale=" in args[vf_idx + 1]
        assert "640" in args[vf_idx + 1]
        assert "-c:v" in args
        codec_idx = args.index("-c:v")
        assert args[codec_idx + 1] == "libwebp"
        assert "-quality" in args
        q_idx = args.index("-quality")
        assert args[q_idx + 1] == "75"
        assert args[-1] == "/media/1_screenshot.webp"
