from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.target_image_dtos import ImageOptionDTO, TargetImageOptionsDTO
from backend.domain.exceptions import (
    CandidateNotFoundError,
    ImageSearchError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.target_image_source import TargetImageSource

logger = logging.getLogger(__name__)


class SearchTargetImagesUseCase:
    """Collects pictures for a target from every source, in source order.

    The target itself is searched unless a free-text query narrows it down, e.g. to
    one meaning of a word that has several. A failing source is skipped, so one
    broken source never hides the others.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        image_sources: Sequence[TargetImageSource],
    ) -> None:
        self._candidate_repo = candidate_repo
        self._image_sources = image_sources

    def execute(self, candidate_id: int, query: str | None = None) -> TargetImageOptionsDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        search = (query or "").strip() or candidate.lemma

        options: list[ImageOptionDTO] = []
        seen_urls: set[str] = set()
        failures: list[ImageSearchError] = []
        for source in self._image_sources:
            try:
                found = source.find_images(search)
            except ImageSearchError as e:
                logger.warning("search_target_images: %s failed for %r: %s",
                               type(source).__name__, search, e)
                failures.append(e)
                continue
            for image in found:
                if image.url not in seen_urls:
                    seen_urls.add(image.url)
                    options.append(ImageOptionDTO(url=image.url, provider=image.provider.value))

        if failures and len(failures) == len(self._image_sources):
            raise ImageSearchError(f"No picture source answered for {search!r}")
        logger.info("search_target_images: %d pictures for %r (candidate %d)",
                    len(options), search, candidate_id)
        return TargetImageOptionsDTO(query=search, options=options)
