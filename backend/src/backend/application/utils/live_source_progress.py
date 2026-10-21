"""The progress of sources computed from the facts, the way the screens computed it before
the stored projection: what the live references order sources by, so that nothing they
compute is read from the projection they are checked against."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.utils.source_progress import SourceProgress
from backend.domain.services.card_view import stored_decided
from backend.domain.value_objects.decision_progress import DecisionProgress

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.card_query import CardQuery


class LiveSourceProgress:
    """The shown cards of the sources, each knowing whether its word is done elsewhere,
    put into sections by the sorter."""

    def __init__(
        self, card_query: CardQuery, sorter: CandidateSorter, vocabulary: UserVocabulary,
    ) -> None:
        self._card_query = card_query
        self._sorter = sorter
        self._vocabulary = vocabulary

    def of_sources(self, source_ids: Collection[int]) -> dict[int, SourceProgress]:
        found = self._card_query.shown_cards(list(source_ids))
        knowledge = self._vocabulary.knowledge()
        cards = {
            source_id: [
                card if stored_decided(card.word_status)
                else replace(card, elsewhere=knowledge.of(card.lemma).elsewhere)
                for card in of_source
            ]
            for source_id, of_source in found.items()
        }
        progress = self._sorter.progress(cards)
        return {
            source_id: SourceProgress(
                progress.get(source_id, DecisionProgress()), len(cards.get(source_id, [])),
            )
            for source_id in source_ids
        }
