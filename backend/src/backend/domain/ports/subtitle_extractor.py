from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


class SubtitleExtractor(ABC):
    """Extracts subtitle data from video files."""

    @abstractmethod
    def list_tracks(self, video_path: str) -> list[SubtitleTrackInfo]:
        """Return the text subtitle tracks embedded in the video; picture ones can't be read."""

    @abstractmethod
    def extract(self, video_path: str, track: SubtitleTrackInfo) -> str:
        """Extract the subtitle track as text in a subtitle format, e.g. SRT or ASS."""

    @abstractmethod
    def frame_rate(self, video_path: str) -> float | None:
        """Frames per second of the video, if it tells."""
