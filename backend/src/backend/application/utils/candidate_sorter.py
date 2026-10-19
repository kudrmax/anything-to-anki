from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_USAGE_GROUP_ORDER,
    USAGE_GROUP_ORDER_SETTING,
)
from backend.domain.services import candidate_sorting
from backend.domain.services.candidate_sections import card_section
from backend.domain.services.card_view import progress
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.candidate_sections import ShownCardFacts
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.review_card import ReviewCard


@dataclass(frozen=True)
class ArrangedCards:
    """Cards in review order, each with its section (by phrase id)."""

    cards: list[ReviewCard]
    sections: dict[int, CandidateSection]

    def section(self, card: ReviewCard) -> CandidateSection:
        return self.sections[card.phrase_id]

    def progress(self) -> DecisionProgress:
        """How far the user got: Reviewed among Reviewed and open Ready."""
        return progress(self.sections.values())


class CandidateSorter:
    """Puts cards in the order the user picked and into the sections their phrases earned.

    Text order has no sections in its order but Reviewed: done cards go below open ones. A
    done card is in Reviewed in every order.
    """

    def __init__(
        self,
        settings_repo: SettingsRepository,
        knowledge: UserKnowledgeReader,
    ) -> None:
        self._settings_repo = settings_repo
        self._knowledge = knowledge

    def arrange(
        self,
        cards: list[ReviewCard],
        order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> ArrangedCards:
        knowledge = self._knowledge.current()
        if order == CandidateSortOrder.CHRONOLOGICAL:
            ordered = candidate_sorting.sort_chronologically(cards)
        elif order == CandidateSortOrder.KEY_WORDS:
            ordered = candidate_sorting.sort_by_key_words(
                cards, knowledge=knowledge,
            )
        else:
            ordered = candidate_sorting.sort_by_relevance(
                cards,
                usage_order=self._usage_order(),
                knowledge=knowledge,
            )
        return ArrangedCards(
            cards=ordered,
            sections={c.phrase_id: card_section(c) for c in ordered},
        )

    def section(self, card: ReviewCard) -> CandidateSection:
        """The section of one card: Reviewed once done, else the one its phrase earned."""
        return card_section(card)

    def progress(
        self, cards_by_source: Mapping[int, Sequence[ShownCardFacts]],
    ) -> dict[int, DecisionProgress]:
        """Progress of each source from its cards."""
        return {
            source_id: progress(card_section(card) for card in cards)
            for source_id, cards in cards_by_source.items()
        }

    def _usage_order(self) -> list[str]:
        raw = self._settings_repo.get(USAGE_GROUP_ORDER_SETTING)
        return json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER

