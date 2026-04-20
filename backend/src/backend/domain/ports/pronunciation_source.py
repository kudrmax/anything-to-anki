from __future__ import annotations

from abc import ABC, abstractmethod


class PronunciationSource(ABC):
    """Port for looking up pronunciation audio URLs by lemma."""

    @abstractmethod
    def get_audio_urls(self, lemma: str) -> tuple[str | None, str | None]:
        """Return (us_url, uk_url) for the given lemma. None if not available."""
        ...
