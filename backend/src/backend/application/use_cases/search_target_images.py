from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_IMAGES_PER_SOURCE,
    IMAGES_PER_SOURCE_SETTING,
)
from backend.application.dto.target_image_dtos import ImageOptionDTO, TargetImageOptionsDTO
from backend.domain.exceptions import CandidateNotFoundError, ImageSearchError
from backend.domain.services.image_option_ranking import rank_image_options

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.target_image_source import TargetImageSource
    from backend.domain.value_objects.image_option import ImageOption

logger = logging.getLogger(__name__)


class SearchTargetImagesUseCase:
    """Asks every picture source at once and ranks what they offer.

    The window opens as fast as the slowest source answers, not the sum of them.
    The target itself is searched unless a free-text query narrows it down, e.g. to
    one meaning of a word that has several. A failing source is skipped, so one
    broken source never hides the others.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        image_sources: Sequence[TargetImageSource],
    ) -> None:
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._image_sources = image_sources

    def execute(self, candidate_id: int, query: str | None = None) -> TargetImageOptionsDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        search = (query or "").strip() or candidate.lemma

        limit = self._images_per_source()
        with ThreadPoolExecutor(max_workers=max(1, len(self._image_sources))) as pool:
            answers = list(pool.map(
                lambda source: self._ask(source, search, limit), self._image_sources,
            ))

        found = [answer for answer in answers if answer is not None]
        if self._image_sources and not found:
            raise ImageSearchError(f"No picture source answered for {search!r}")
        options = [
            ImageOptionDTO(url=o.url, provider=o.provider.value) for o in rank_image_options(found)
        ]
        logger.info("search_target_images: %d pictures for %r (candidate %d)",
                    len(options), search, candidate_id)
        return TargetImageOptionsDTO(query=search, options=options)

    @staticmethod
    def _ask(source: TargetImageSource, word: str, limit: int) -> list[ImageOption] | None:
        try:
            return source.find_images(word, limit)
        except ImageSearchError as e:
            logger.warning("search_target_images: %s failed for %r: %s",
                           type(source).__name__, word, e)
            return None

    def _images_per_source(self) -> int:
        raw = self._settings_repo.get(IMAGES_PER_SOURCE_SETTING)
        return int(raw) if raw and raw.isdigit() else DEFAULT_IMAGES_PER_SOURCE
