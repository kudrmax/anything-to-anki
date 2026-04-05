from __future__ import annotations

from abc import ABC, abstractmethod


class SourceParser(ABC):
    """Pre-processes source-specific format into plain text before general cleaning."""

    @abstractmethod
    def parse(self, raw_text: str) -> str:
        """Convert source-specific format to plain text."""
