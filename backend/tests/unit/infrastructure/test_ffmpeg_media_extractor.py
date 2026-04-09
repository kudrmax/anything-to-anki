# backend/tests/unit/infrastructure/test_ffmpeg_media_extractor.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.infrastructure.adapters.ffmpeg_media_extractor import (
    _AUDIO_BITRATE,
    _AUDIO_CHANNELS,
    _SCREENSHOT_MAX_WIDTH,
    _SCREENSHOT_WEBP_QUALITY,
    FfmpegMediaExtractor,
)


@pytest.mark.unit
class TestFfmpegMediaExtractorScreenshot:
    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_screenshot_uses_webp_with_scale_and_quality(
        self, mock_run: MagicMock,
    ) -> None:
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
        assert str(_SCREENSHOT_MAX_WIDTH) in args[vf_idx + 1]
        assert "-c:v" in args
        codec_idx = args.index("-c:v")
        assert args[codec_idx + 1] == "libwebp"
        assert "-quality" in args
        q_idx = args.index("-quality")
        assert args[q_idx + 1] == str(_SCREENSHOT_WEBP_QUALITY)
        assert args[-1] == "/media/1_screenshot.webp"
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("check") is True
        assert kwargs.get("capture_output") is True


@pytest.mark.unit
class TestFfmpegMediaExtractorAudio:
    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_audio_uses_aac_mono_96k_no_track_index(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        extractor = FfmpegMediaExtractor()

        extractor.extract_audio("/videos/movie.mkv", 1000, 4000, "/media/1_audio.m4a")

        args = mock_run.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "-ss" in args and "1.0" in args
        assert "-to" in args and "4.0" in args
        assert "-vn" in args
        assert "-c:a" in args
        codec_idx = args.index("-c:a")
        assert args[codec_idx + 1] == "aac"
        assert "-b:a" in args
        bitrate_idx = args.index("-b:a")
        assert args[bitrate_idx + 1] == _AUDIO_BITRATE
        assert "-ac" in args
        ac_idx = args.index("-ac")
        assert args[ac_idx + 1] == str(_AUDIO_CHANNELS)
        # no -map since track_index is None
        assert "-map" not in args
        assert args[-1] == "/media/1_audio.m4a"

        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("check") is True
        assert kwargs.get("capture_output") is True

    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_audio_uses_map_when_track_index_given(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        extractor = FfmpegMediaExtractor()

        extractor.extract_audio(
            "/videos/movie.mkv", 1000, 4000, "/media/1_audio.m4a", audio_track_index=2,
        )

        args = mock_run.call_args[0][0]
        assert "-map" in args
        map_idx = args.index("-map")
        assert args[map_idx + 1] == "0:a:2"
        # Ensure -map appears BEFORE the audio codec args
        codec_idx = args.index("-c:a")
        assert map_idx < codec_idx
