from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.value_objects.image_option import ImageOption
    from backend.domain.value_objects.picture_search import PictureSearch


class BackgroundPictureSearches(ABC):
    """Port: picture searches that run apart from requests. A request only reads how a
    search stands, so a slow picture source never holds it."""

    @abstractmethod
    def search(self, key: str, find: Callable[[], Sequence[ImageOption]]) -> PictureSearch:
        """How the search under `key` stands now. One not asked for yet starts `find` in the
        background; `find` raises ImageSearchError when it fails."""
