from abc import ABC, abstractmethod

from backend.domain.value_objects.source_type import SourceType


class TextCleaner(ABC):
    """Port for cleaning raw text (layer 2 of the pipeline)."""

    @abstractmethod
    def clean(self, raw_text: str, source_type: SourceType = SourceType.TEXT) -> str:
        """Remove timecodes, tags, duplicate lines, normalize whitespace."""
