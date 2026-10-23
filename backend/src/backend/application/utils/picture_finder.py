from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_IMAGES_PER_SOURCE, IMAGES_PER_SOURCE_SETTING
from backend.domain.exceptions import ImageSearchError
from backend.domain.services.image_option_ranking import rank_image_options

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.target_image_source import TargetImageSource
    from backend.domain.value_objects.image_option import ImageOption

logger = logging.getLogger(__name__)


class PictureFinder:
    """Asks every picture source at once and ranks what they offer.

    The search takes as long as the slowest source, not the sum of them. A failing source
    is skipped, so one broken source never hides the others."""

    def __init__(self, image_sources: Sequence[TargetImageSource]) -> None:
        self._image_sources = image_sources

    def find(self, search: str, limit: int) -> list[ImageOption]:
        """The pictures for the search, best first. ImageSearchError when no source
        answered."""
        with ThreadPoolExecutor(max_workers=max(1, len(self._image_sources))) as pool:
            answers = list(pool.map(
                lambda source: self._ask(source, search, limit), self._image_sources,
            ))
        found = [answer for answer in answers if answer is not None]
        if self._image_sources and not found:
            raise ImageSearchError(f"No picture source answered for {search!r}")
        return rank_image_options(found)

    @staticmethod
    def _ask(source: TargetImageSource, word: str, limit: int) -> list[ImageOption] | None:
        try:
            return source.find_images(word, limit)
        except ImageSearchError as e:
            logger.warning("search_target_images: %s failed for %r: %s",
                           type(source).__name__, word, e)
            return None


def images_per_source(settings_repo: SettingsRepository) -> int:
    """How many pictures each source is asked for, as the settings say."""
    raw = settings_repo.get(IMAGES_PER_SOURCE_SETTING)
    return int(raw) if raw and raw.isdigit() else DEFAULT_IMAGES_PER_SOURCE
