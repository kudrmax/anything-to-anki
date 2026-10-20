from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.card_state_rows import CardStates, StoredCardStates


class CardStateStore(ABC):
    """Port for the stored projection of card state. Only the projector writes it; the
    rules never read it."""

    @abstractmethod
    def next_revision(self) -> int:
        """Moves the projection's revision one up and returns the new one."""

    @abstractmethod
    def replace_all(self, states: CardStates, revision: int) -> None:
        """Every row of the projection becomes `states`, each written at `revision`. A card
        stored before and missing from `states` stays as a removed row at `revision`."""

    @abstractmethod
    def read_all(self) -> StoredCardStates:
        """Every stored row, removed cards included."""
