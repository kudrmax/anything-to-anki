from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.card_change import CardChange


class ChangeRecorder(ABC):
    """Port where the owners of facts note what they changed, for whoever keeps card state
    in step with those facts."""

    @abstractmethod
    def record(self, change: CardChange) -> None:
        """Notes one change."""

    @abstractmethod
    def drain(self) -> tuple[CardChange, ...]:
        """Takes the recorded changes in the order they came, each exact duplicate once,
        and leaves the recorder empty."""
