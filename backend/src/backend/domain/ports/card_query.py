from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.review_card import CardRow
    from backend.domain.value_objects.shown_place import ShownPlace


class CardQuery(ABC):
    """Port for light projections of the cards of sources — their shown phrases — without
    loading what was made for them."""

    @abstractmethod
    def shown_cards(self, source_ids: list[int]) -> dict[int, list[CardRow]]:
        """Source id → its cards; a source without cards is left out. `elsewhere` is not
        filled: it depends on what the user knows."""

    @abstractmethod
    def learn_counts(self, source_ids: list[int]) -> dict[int, int]:
        """Source id → how many of its words are to learn; a source without any is left out."""

    @abstractmethod
    def shown_places(self, source_id: int) -> list[ShownPlace]:
        """The shown phrases of the source that stand in its document."""
