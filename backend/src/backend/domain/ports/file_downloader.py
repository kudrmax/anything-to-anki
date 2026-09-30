from __future__ import annotations

from abc import ABC, abstractmethod


class FileDownloader(ABC):
    """Port for downloading a file from a URL to a local path."""

    @abstractmethod
    def download(self, url: str, dest: str) -> None:
        """Download the file to the given path. Raises on failure."""
