from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.card_layout import CardLayout


class CardLayoutRepository(ABC):
    """Port for the user's card layout: the default one until the user changes it."""

    @abstractmethod
    def get(self) -> CardLayout: ...

    @abstractmethod
    def save(self, layout: CardLayout) -> None: ...
