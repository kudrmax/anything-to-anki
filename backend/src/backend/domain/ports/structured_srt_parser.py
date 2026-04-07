from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.parsed_srt import ParsedSrt


class StructuredSrtParser(ABC):
    """Parses SRT text into cleaned text with per-block char offsets."""

    @abstractmethod
    def parse_structured(self, raw_text: str) -> ParsedSrt: ...
