from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.audio_track_info import AudioTrackInfo


class AudioTrackLister(ABC):
    """Lists audio tracks embedded in a video file."""

    @abstractmethod
    def list_audio_tracks(self, video_path: str) -> list[AudioTrackInfo]:
        """Return all audio tracks embedded in the video."""
