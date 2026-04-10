from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.value_objects.fetched_subtitles import FetchedSubtitles


class UrlSourceFetcher(ABC):
    """Port for fetching subtitles from URL-based sources."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Whether this fetcher can process the given URL."""

    @abstractmethod
    def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
        """Fetch subtitles. Raises SubtitlesNotAvailableError if none found."""
