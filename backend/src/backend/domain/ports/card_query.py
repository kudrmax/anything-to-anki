from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection

    from backend.domain.value_objects.generated_parts import GeneratedParts
    from backend.domain.value_objects.review_card import CardRow, CardTargetRow
    from backend.domain.value_objects.shown_place import ShownPlace


class CardQuery(ABC):
    """Port for light projections of the cards of sources — their shown phrases — with only
    whether something was made for them, not what."""

    @abstractmethod
    def shown_cards(self, source_ids: list[int]) -> dict[int, list[CardRow]]:
        """Source id → its cards; a source without cards is left out. `elsewhere` is not
        filled: it depends on what the user knows."""

    @abstractmethod
    def shown_cards_of_phrases(self, phrase_ids: Collection[int]) -> list[CardRow]:
        """The cards among these phrases: a phrase not shown is left out. `elsewhere` is
        not filled."""

    @abstractmethod
    def shown_cards_of_words(self, word_ids: Collection[int]) -> list[CardRow]:
        """Every card of these words. `elsewhere` is not filled."""

    @abstractmethod
    def generated_parts(self, phrase_ids: Collection[int]) -> dict[int, GeneratedParts]:
        """What generation made for these phrases, by phrase id: a phrase not shown is left
        out."""

    @abstractmethod
    def card_targets(self, phrase_ids: Collection[int]) -> list[CardTargetRow]:
        """The cards among these phrases without their phrases: a phrase not shown is left
        out."""

    @abstractmethod
    def card_targets_of_words(self, word_ids: Collection[int]) -> list[CardTargetRow]:
        """Every card of these words, without its phrase."""

    @abstractmethod
    def learn_counts(self, source_ids: list[int]) -> dict[int, int]:
        """Source id → how many of its words are to learn; a source without any is left out."""

    @abstractmethod
    def shown_places(self, source_id: int) -> list[ShownPlace]:
        """The shown phrases of the source that stand in its document."""
