from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.image_option import ImageOption


class TargetImageSource(ABC):
    """Port for finding pictures that illustrate a word."""

    @abstractmethod
    def find_images(self, word: str) -> list[ImageOption]:
        """Pictures for the word, best first. Raises ImageSearchError when the lookup fails."""

    @abstractmethod
    def owns(self, url: str) -> bool:
        """Whether the URL is one this source hands out — only such URLs get downloaded."""
