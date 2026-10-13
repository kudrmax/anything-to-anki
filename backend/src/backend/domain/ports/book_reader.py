from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.book import Book


class BookReader(ABC):
    """Reads the prose of a book file, split into chapters."""

    @abstractmethod
    def read(self, path: str) -> Book:
        """Raises BookReadError if the file can't be read as a book."""
