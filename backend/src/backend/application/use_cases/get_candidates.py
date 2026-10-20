from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.utils.card_views import CardViews
    from backend.domain.value_objects.source_scope import SourceScope


class GetCandidatesUseCase:
    """The cards of a set of sources — their shown phrases — in review order."""

    def __init__(self, card_views: CardViews) -> None:
        self._card_views = card_views

    def execute(
        self,
        scope: SourceScope,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[CardDTO]:
        return self._card_views.listed(scope, sort_order).cards
