from __future__ import annotations

from enum import Enum


class ImageProvider(Enum):
    """Where a picture offered for a target comes from."""

    WIKTIONARY = "wiktionary"
    BING = "bing"
    YANDEX = "yandex"

    @property
    def is_dictionary(self) -> bool:
        """Editors chose the picture for exactly this word, unlike a search engine's guess."""
        return self is ImageProvider.WIKTIONARY
