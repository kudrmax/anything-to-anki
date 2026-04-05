from __future__ import annotations

from abc import ABC, abstractmethod


class TextCleaner(ABC):
    """Port for cleaning raw text (layer 2 of the pipeline)."""

    @abstractmethod
    def clean(self, raw_text: str) -> str:
        """Remove timecodes, tags, duplicate lines, normalize whitespace."""
