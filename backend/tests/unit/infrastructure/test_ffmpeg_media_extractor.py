# backend/tests/unit/infrastructure/test_ffmpeg_media_extractor.py
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.domain.ports.card_picture_encoder import CardPictureEncoder
from backend.infrastructure.adapters.ffmpeg_media_extractor import (
    _AUDIO_BITRATE,
    _AUDIO_CHANNELS,
    _SCREENSHOT_FRAME_CODEC,
    _SCREENSHOT_PIPE_FORMAT,
    _SCREENSHOT_PIPE_TARGET,
    FfmpegMediaExtractor,
)
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path



class _RecordingEncoder(CardPictureEncoder):
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str]] = []

    def encode(self, picture: bytes, out_path: str) -> None:
        self.calls.append((picture, out_path))


def _png_frame() -> bytes:
    """Кадр, который в реальности приходит от ffmpeg через stdout."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.unit
class TestFfmpegMediaExtractorScreenshot:
    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_screenshot_pipes_full_frame_to_the_card_picture_encoder(
        self, mock_run: MagicMock, tmp_path: Path,
    ) -> None:
        frame = _png_frame()
        mock_run.return_value = MagicMock(returncode=0, stdout=frame, stderr=b"")
        out_path = tmp_path / "1_screenshot.webp"
        encoder = _RecordingEncoder()
        extractor = FfmpegMediaExtractor(encoder)

        extractor.extract_screenshot("/videos/movie.mkv", 5000, str(out_path))

        args = mock_run.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "-ss" in args
        assert "5.0" in args
        assert "-i" in args
        assert "/videos/movie.mkv" in args
        assert "-vframes" in args
        # ffmpeg only decodes: sizing and WebP are the encoder's job
        assert "-vf" not in args
        format_idx = args.index("-f")
        assert args[format_idx + 1] == _SCREENSHOT_PIPE_FORMAT
        codec_idx = args.index("-c:v")
        assert args[codec_idx + 1] == _SCREENSHOT_FRAME_CODEC
        assert args[-1] == _SCREENSHOT_PIPE_TARGET
        assert str(out_path) not in args
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("check") is True
        assert kwargs.get("capture_output") is True

        assert encoder.calls == [(frame, str(out_path))]

    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_screenshot_raises_and_logs_when_no_frame_decoded(
        self, mock_run: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Пустой вывод при коде возврата 0 — ошибка, а не успешный скриншот."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout=b"", stderr=b"Output file is empty, nothing was encoded",
        )
        out_path = tmp_path / "1_screenshot.webp"
        encoder = _RecordingEncoder()
        extractor = FfmpegMediaExtractor(encoder)

        with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
            extractor.extract_screenshot("/videos/movie.mkv", 5000, str(out_path))

        assert not out_path.exists()
        assert encoder.calls == []
        assert "Output file is empty" in caplog.text


@pytest.mark.unit
class TestFfmpegMediaExtractorAudio:
    @patch("backend.infrastructure.adapters.ffmpeg_media_extractor.subprocess.run")
    def test_extract_audio_uses_aac_mono_96k_no_track_index(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        extractor = FfmpegMediaExtractor(_RecordingEncoder())

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
        extractor = FfmpegMediaExtractor(_RecordingEncoder())

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
