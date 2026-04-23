from __future__ import annotations

from abc import ABC, abstractmethod


class FileReader(ABC):
    """Reads files from the local filesystem."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists at path."""

    @abstractmethod
    def read_text(self, path: str) -> str:
        """Read file content as text. Raises FileNotFoundError if missing."""
