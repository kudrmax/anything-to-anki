from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.source_input import SourceInput


class FormatDetector(ABC):
    """Tells how an input is laid out."""

    @abstractmethod
    def detect(self, source_input: SourceInput) -> Format:
        """Raises UnsupportedUrlError for a link no reader can follow."""
