from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from backend.domain.ports.media_extractor import MediaExtractor

if TYPE_CHECKING:
    from backend.domain.ports.card_picture_encoder import CardPictureEncoder

logger = logging.getLogger(__name__)

_SCREENSHOT_FRAME_CODEC: str = "png"
_SCREENSHOT_PIPE_FORMAT: str = "image2pipe"
_SCREENSHOT_PIPE_TARGET: str = "-"
_AUDIO_BITRATE: str = "96k"
_AUDIO_CHANNELS: int = 1


class FfmpegMediaExtractor(MediaExtractor):
    """Generates screenshots and audio clips from video files using ffmpeg."""

    def __init__(self, picture_encoder: CardPictureEncoder) -> None:
        self._picture_encoder = picture_encoder

    def extract_screenshot(self, video_path: str, timestamp_ms: int, out_path: str) -> None:
        """Grab a full-size frame with ffmpeg and hand it to the card picture encoder.

        ffmpeg only decodes here — every build can do that. Scaling and WebP
        encoding are deliberately kept out of ffmpeg: its libwebp is an optional
        build dependency, and homebrew/core dropped it, which silently broke
        screenshot generation. The encoder also shrinks pictures picked for a
        target, so every card picture gets the same size and format.
        """
        ts_s = timestamp_ms / 1000.0
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts_s),
            "-i", video_path,
            "-vframes", "1",
            "-f", _SCREENSHOT_PIPE_FORMAT,
            "-c:v", _SCREENSHOT_FRAME_CODEC,
            _SCREENSHOT_PIPE_TARGET,
        ]
        logger.debug("ffmpeg.screenshot: running (out=%s, ts_ms=%d)", out_path, timestamp_ms)
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            logger.exception(
                "ffmpeg.screenshot: failed (out=%s, ts_ms=%d, stderr=%s)",
                out_path, timestamp_ms, stderr[:1000],
            )
            raise

        if not result.stdout:
            # Asking for a timestamp past the end of the video makes ffmpeg
            # encode nothing and still exit with 0, so check=True stays silent.
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            logger.error(
                "ffmpeg.screenshot: no frame decoded (out=%s, ts_ms=%d, stderr=%s)",
                out_path, timestamp_ms, stderr[:1000],
            )
            raise RuntimeError(f"ffmpeg decoded no frame at {timestamp_ms} ms of {video_path}")

        self._picture_encoder.encode(result.stdout, out_path)

    def extract_audio(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        out_path: str,
        audio_track_index: int | None = None,
    ) -> None:
        start_s = start_ms / 1000.0
        end_s = end_ms / 1000.0
        args: list[str] = [
            "ffmpeg", "-y",
            "-ss", str(start_s),
            "-to", str(end_s),
            "-i", video_path,
            "-vn",
        ]
        if audio_track_index is not None:
            args += ["-map", f"0:a:{audio_track_index}"]
        args += [
            "-c:a", "aac",
            "-b:a", _AUDIO_BITRATE,
            "-ac", str(_AUDIO_CHANNELS),
            out_path,
        ]
        logger.debug(
            "ffmpeg.audio: running (out=%s, start_ms=%d, end_ms=%d, track=%s)",
            out_path, start_ms, end_ms, audio_track_index,
        )
        try:
            subprocess.run(args, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            logger.exception(
                "ffmpeg.audio: failed (out=%s, start_ms=%d, end_ms=%d, stderr=%s)",
                out_path, start_ms, end_ms, stderr[:1000],
            )
            raise
