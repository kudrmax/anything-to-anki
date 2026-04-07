from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


class SubtitleExtractor(ABC):
    """Extracts subtitle data from video files."""

    @abstractmethod
    def list_tracks(self, video_path: str) -> list[SubtitleTrackInfo]:
        """Return all subtitle tracks embedded in the video."""

    @abstractmethod
    def extract(self, video_path: str, track_index: int) -> str:
        """Extract subtitle track as raw SRT text."""
