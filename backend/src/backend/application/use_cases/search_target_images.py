from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.target_image_dtos import ImageOptionDTO, TargetImageOptionsDTO
from backend.application.utils.picture_finder import PictureFinder, images_per_source
from backend.domain.exceptions import CandidateNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.target_image_source import TargetImageSource

logger = logging.getLogger(__name__)


class SearchTargetImagesUseCase:
    """The pictures of the picker window, searched while the user waits for them.

    The target itself is searched unless a free-text query narrows it down, e.g. to
    one meaning of a word that has several."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        image_sources: Sequence[TargetImageSource],
    ) -> None:
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._finder = PictureFinder(image_sources)

    def execute(self, candidate_id: int, query: str | None = None) -> TargetImageOptionsDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        search = (query or "").strip() or candidate.lemma
        found = self._finder.find(search, images_per_source(self._settings_repo))
        options = [ImageOptionDTO(url=o.url, provider=o.provider.value) for o in found]
        logger.info("search_target_images: %d pictures for %r (candidate %d)",
                    len(options), search, candidate_id)
        return TargetImageOptionsDTO(query=search, options=options)
