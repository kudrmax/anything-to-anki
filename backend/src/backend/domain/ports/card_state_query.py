from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

    from backend.domain.value_objects.by_step import SectionsByStep
    from backend.domain.value_objects.generation_tally import GenerationTally
    from backend.domain.value_objects.ordered_card import OrderedCard
    from backend.domain.value_objects.section_tally import SectionTally


class CardStateQuery(ABC):
    """Read side of the stored projection, for the screens. The rules never read it.

    Only live rows count: a removed card is gone for the screens."""

    @abstractmethod
    def revision(self) -> int:
        """The projection's current revision."""

    @abstractmethod
    def section_tallies(self, source_ids: Collection[int]) -> dict[int, SectionTally]:
        """The cards of each source counted by their stored sections; a source without
        cards is left out."""

    @abstractmethod
    def done_of_sources(self, source_ids: Collection[int]) -> dict[int, bool]:
        """Phrase id → whether its card is done, for every card of these sources."""

    @abstractmethod
    def order_rows(self, source_ids: Sequence[int]) -> list[OrderedCard]:
        """Every card of these sources with what the review order reads of it: its stored
        standing, the facts of its word and the place of its phrase. In no given order."""

    @abstractmethod
    def generation_tallies(
        self, source_ids: Collection[int], ready: Callable[[SectionsByStep], bool],
    ) -> dict[int, GenerationTally]:
        """The cards in play of each source counted, for every kind, by what tells their
        generation state: the stored results and the jobs of the queue. A kind of a word
        counts the words with a card in play. `ready`: whether a card in play with these
        open sections wants ready generation; a word does when one of its cards does. A
        source without cards in play is left out."""
