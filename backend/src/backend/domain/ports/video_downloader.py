from __future__ import annotations

from abc import ABC, abstractmethod


class VideoDownloader(ABC):
    """Port for downloading video from URL to local file."""

    @abstractmethod
    def download(self, url: str, output_path: str) -> None:
        """Download video to the given path. Raises on failure."""
