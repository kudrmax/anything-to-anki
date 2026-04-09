from __future__ import annotations

import logging
import subprocess

from backend.domain.ports.media_extractor import MediaExtractor

logger = logging.getLogger(__name__)

_SCREENSHOT_MAX_WIDTH: int = 640
_SCREENSHOT_WEBP_QUALITY: int = 75
_AUDIO_BITRATE: str = "96k"
_AUDIO_CHANNELS: int = 1


class FfmpegMediaExtractor(MediaExtractor):
    """Generates screenshots and audio clips from video files using ffmpeg."""

    def extract_screenshot(self, video_path: str, timestamp_ms: int, out_path: str) -> None:
        ts_s = timestamp_ms / 1000.0
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts_s),
            "-i", video_path,
            "-vframes", "1",
            "-vf", f"scale='min({_SCREENSHOT_MAX_WIDTH},iw)':'-2'",
            "-c:v", "libwebp",
            "-quality", str(_SCREENSHOT_WEBP_QUALITY),
            out_path,
        ]
        logger.debug("ffmpeg.screenshot: running (out=%s, ts_ms=%d)", out_path, timestamp_ms)
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            logger.exception(
                "ffmpeg.screenshot: failed (out=%s, ts_ms=%d, stderr=%s)",
                out_path, timestamp_ms, stderr[:1000],
            )
            raise

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
