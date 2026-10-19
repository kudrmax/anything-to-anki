from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.services.card_view import stored_decided
from backend.domain.value_objects.decision_progress import DecisionProgress

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.decided_elsewhere import DecidedElsewhere
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.value_objects.review_card import CardRow


class ReviewProgress:
    """How far the user got with a source, by what they know right now. Everything that
    shows or sums progress — a source, its review screen, a collection — takes it from here.

    Reads the cards light: the shown phrases and the facts of their words, nothing made
    for them."""

    def __init__(
        self,
        card_query: CardQuery,
        candidate_sorter: CandidateSorter,
        decided_elsewhere: DecidedElsewhere,
    ) -> None:
        self._card_query = card_query
        self._candidate_sorter = candidate_sorter
        self._decided_elsewhere = decided_elsewhere

    def of_sources(self, source_ids: list[int]) -> dict[int, DecisionProgress]:
        progress = self.progress_of(self.cards(source_ids))
        return {source_id: progress.get(source_id, DecisionProgress()) for source_id in source_ids}

    def progress_of(self, cards: dict[int, list[CardRow]]) -> dict[int, DecisionProgress]:
        """Progress from cards read with `cards`."""
        return self._candidate_sorter.progress(cards)

    def cards(self, source_ids: list[int]) -> dict[int, list[CardRow]]:
        """The cards of the sources, each knowing whether its word is done elsewhere."""
        found = self._card_query.shown_cards(source_ids)
        open_lemmas = {
            card.lemma
            for cards in found.values() for card in cards
            if not stored_decided(card.word_status)
        }
        elsewhere = self._decided_elsewhere.of_lemmas(open_lemmas)
        return {
            source_id: [
                replace(card, elsewhere=elsewhere[card.lemma])
                if not stored_decided(card.word_status) and elsewhere[card.lemma] is not None
                else card
                for card in cards
            ]
            for source_id, cards in found.items()
        }
