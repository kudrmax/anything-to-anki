from __future__ import annotations

import subprocess

from backend.domain.ports.media_extractor import MediaExtractor

_SCREENSHOT_MAX_WIDTH: int = 640
_SCREENSHOT_WEBP_QUALITY: int = 75
_AUDIO_BITRATE: str = "96k"
_AUDIO_CHANNELS: int = 1


class FfmpegMediaExtractor(MediaExtractor):
    """Generates screenshots and audio clips from video files using ffmpeg."""

    def extract_screenshot(self, video_path: str, timestamp_ms: int, out_path: str) -> None:
        ts_s = timestamp_ms / 1000.0
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(ts_s),
                "-i", video_path,
                "-vframes", "1",
                "-vf", f"scale='min({_SCREENSHOT_MAX_WIDTH},iw)':'-2'",
                "-c:v", "libwebp",
                "-quality", str(_SCREENSHOT_WEBP_QUALITY),
                out_path,
            ],
            capture_output=True,
            check=True,
        )

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
        subprocess.run(args, capture_output=True, check=True)
