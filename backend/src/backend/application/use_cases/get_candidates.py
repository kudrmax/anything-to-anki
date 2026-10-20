from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.domain.ports.source_repository import SourceRepository


class GetCandidatesUseCase:
    """The cards of a source — its shown phrases — in review order."""

    def __init__(self, source_repo: SourceRepository, card_views: CardViews) -> None:
        self._source_repo = source_repo
        self._card_views = card_views

    def execute(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[CardDTO]:
        if self._source_repo.get_by_id(source_id) is None:
            raise SourceNotFoundError(source_id)
        return self._card_views.listed(SourceScope.source(source_id), sort_order).cards
