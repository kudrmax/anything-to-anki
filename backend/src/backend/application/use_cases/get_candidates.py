from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import DEFAULT_USAGE_GROUP_ORDER
from backend.application.dto.source_dtos import StoredCandidateDTO, stored_candidate_to_dto
from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


class GetCandidatesUseCase:
    """Retrieves candidates for a given source."""

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[StoredCandidateDTO]:
        from backend.domain.services.candidate_sorting import (
            sort_by_relevance,
            sort_chronologically,
        )
        from backend.domain.value_objects.candidate_sort_order import (
            CandidateSortOrder as SortEnum,
        )

        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        candidates = self._candidate_repo.get_by_source(source_id)
        if sort_order == SortEnum.CHRONOLOGICAL:
            text = source.cleaned_text or source.raw_text
            candidates = sort_chronologically(candidates, source_text=text)
        else:
            raw = self._settings_repo.get("usage_group_order")
            usage_order: list[str] = json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
            candidates = sort_by_relevance(candidates, usage_order=usage_order)
        return [stored_candidate_to_dto(c) for c in candidates]
