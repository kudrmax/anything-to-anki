from __future__ import annotations

from abc import ABC, abstractmethod


class MediaExtractor(ABC):
    """Generates screenshots and audio clips from video files."""

    @abstractmethod
    def extract_screenshot(self, video_path: str, timestamp_ms: int, out_path: str) -> None:
        """Write a JPEG screenshot at the given timestamp."""

    @abstractmethod
    def extract_audio(
        self,
        video_path: str,
        start_ms: int,
        end_ms: int,
        out_path: str,
        audio_track_index: int | None = None,
    ) -> None:
        """Write an MP3 audio clip for the given time range.

        If audio_track_index is None, ffmpeg picks the default audio stream.
        """
