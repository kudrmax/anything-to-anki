"""The stored card-state projection in tests: rebuilt for data seeded outside the use
cases, or read from cards a unit test gives."""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from backend.domain.ports.card_state_query import CardStateQuery
from backend.domain.value_objects.by_step import SectionsByStep
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS
from backend.domain.value_objects.section_tally import SectionTally
from backend.infrastructure.api.dependencies import get_container

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.services.candidate_sections import ShownCardFacts
    from backend.domain.value_objects.generation_tally import GenerationTally
    from sqlalchemy.orm import Session


def rebuild_projection(session: Session) -> None:
    """The projection computed anew and committed, as the app's start does: the screens
    read it, and rows written straight to the tables never reach it."""
    container = get_container()
    container.knowledge_scope(session).invalidate()
    container.card_state_projector(session).rebuild()
    session.commit()


class LiveSectionTallies(CardStateQuery):
    """The screens' read port over the cards a unit test gives: each card counted in the
    section the sorter puts it in now, the same at every threshold step."""

    def __init__(
        self,
        cards_of: Callable[[list[int]], Mapping[int, Sequence[ShownCardFacts]]],
        sorter: CandidateSorter,
    ) -> None:
        self._cards_of = cards_of
        self._sorter = sorter

    def revision(self) -> int:
        return 0

    def section_tallies(self, source_ids: Collection[int]) -> dict[int, SectionTally]:
        return {
            source_id: SectionTally(Counter(
                SectionsByStep((self._sorter.section(card),) * len(THRESHOLD_STEPS))
                for card in cards
            ))
            for source_id, cards in self._cards_of(list(source_ids)).items()
        }

    def done_of_sources(self, source_ids: Collection[int]) -> dict[int, bool]:
        return {
            card.phrase_id: card.is_done
            for cards in self._cards_of(list(source_ids)).values() for card in cards
        }

    def generation_tallies(
        self, source_ids: Collection[int], ready: Callable[[SectionsByStep], bool],
    ) -> dict[int, GenerationTally]:
        raise NotImplementedError("the screens of these tests do not count generation")


def review_cards_by_source(
    cards: Callable[[list[int]], Sequence[ShownCardFacts]],
) -> Callable[[list[int]], dict[int, list[ShownCardFacts]]]:
    """`cards` of the sources, which tell their source, grouped by it."""
    def by_source(source_ids: list[int]) -> dict[int, list[ShownCardFacts]]:
        grouped: dict[int, list[ShownCardFacts]] = {}
        for card in cards(source_ids):
            grouped.setdefault(card.word.source_id, []).append(card)
        return grouped

    return by_source
