from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_USAGE_GROUP_ORDER,
    USAGE_GROUP_ORDER_SETTING,
)
from backend.domain.services import candidate_sorting
from backend.domain.services.candidate_sections import ready_progress, section_of
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.candidate_sections import ProgressFacts
    from backend.domain.value_objects.candidate_section import CandidateSection
    from backend.domain.value_objects.decision_progress import DecisionProgress
    from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
    from backend.domain.value_objects.review_card import ReviewCard
    from backend.domain.value_objects.user_knowledge import UserKnowledge


@dataclass(frozen=True)
class ArrangedCards:
    """Cards in review order, each with its section (by phrase id)."""

    cards: list[ReviewCard]
    sections: dict[int, CandidateSection]

    def section(self, card: ReviewCard) -> CandidateSection:
        return self.sections[card.phrase_id]

    def progress(self) -> DecisionProgress:
        """How far the user got: done cards among the Ready ones; the rest don't count."""
        return ready_progress((c, self.section(c)) for c in self.cards)


class CandidateSorter:
    """Puts cards in the order the user picked and into sections, by what the user knows now.

    Text order has no sections in its order; done cards go below open ones.
    """

    def __init__(
        self,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        knowledge: UserKnowledgeReader,
    ) -> None:
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver
        self._knowledge = knowledge

    def arrange(
        self,
        cards: list[ReviewCard],
        order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> ArrangedCards:
        knowledge = self._knowledge.current()
        threshold = self._threshold_resolver.resolve()
        if order == CandidateSortOrder.CHRONOLOGICAL:
            ordered = candidate_sorting.sort_chronologically(cards)
        elif order == CandidateSortOrder.KEY_WORDS:
            ordered = candidate_sorting.sort_by_key_words(
                cards, frequent_threshold=threshold, knowledge=knowledge,
            )
        else:
            ordered = candidate_sorting.sort_by_relevance(
                cards,
                usage_order=self._usage_order(),
                frequent_threshold=threshold,
                knowledge=knowledge,
            )
        return ArrangedCards(
            cards=ordered,
            sections={c.phrase_id: section_of(c, knowledge, threshold) for c in ordered},
        )

    def section(self, card: ReviewCard) -> CandidateSection:
        """The section of one card, by what the user knows now."""
        return section_of(card, self._knowledge.current(), self._threshold_resolver.resolve())

    def progress(
        self, cards_by_source: Mapping[int, Sequence[ProgressFacts]],
    ) -> dict[int, DecisionProgress]:
        """Progress of each source from its cards, reading what the user knows once."""
        knowledge = self._knowledge.current()
        threshold = self._threshold_resolver.resolve()
        return {
            source_id: ready_progress(_with_sections(cards, knowledge, threshold))
            for source_id, cards in cards_by_source.items()
        }

    def _usage_order(self) -> list[str]:
        raw = self._settings_repo.get(USAGE_GROUP_ORDER_SETTING)
        return json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER


def _with_sections(
    cards: Sequence[ProgressFacts],
    knowledge: UserKnowledge,
    threshold: FrequentWordThreshold | None,
) -> Iterable[tuple[ProgressFacts, CandidateSection]]:
    return ((card, section_of(card, knowledge, threshold)) for card in cards)
