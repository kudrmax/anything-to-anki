from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.target_image_dtos import ImageOptionDTO, TargetImageSuggestionsDTO
from backend.application.utils.picture_finder import PictureFinder, images_per_source
from backend.domain.exceptions import CandidateNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.background_picture_searches import BackgroundPictureSearches
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.target_image_source import TargetImageSource


class SuggestTargetImagesUseCase:
    """The pictures suggested on a card: searched in the background, answered at once with
    what is found so far. The first ask starts the search; the client asks again while it
    is still going."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        image_sources: Sequence[TargetImageSource],
        searches: BackgroundPictureSearches,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._finder = PictureFinder(image_sources)
        self._searches = searches

    def execute(self, candidate_id: int) -> TargetImageSuggestionsDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        search = candidate.lemma
        limit = images_per_source(self._settings_repo)
        state = self._searches.search(
            f"{search.lower()}:{limit}", lambda: self._finder.find(search, limit),
        )
        return TargetImageSuggestionsDTO(
            status=state.status,
            query=search,
            options=[ImageOptionDTO(url=o.url, provider=o.provider.value) for o in state.options],
        )
