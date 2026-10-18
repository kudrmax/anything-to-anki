from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


class LearningQuery(ABC):
    """Port for the lemmas the user is learning ("учу"), lowercase."""

    @abstractmethod
    def awaiting_export(self) -> frozenset[str]:
        """Words decided Learn or Cloze in any source and not exported yet."""

    @abstractmethod
    def active_since(self) -> Mapping[str, tuple[datetime, ...]]:
        """When each active binding of each lemma was exported, orphaned ones included."""

    def in_anki(self) -> frozenset[str]:
        """Lemmas with an active binding."""
        return frozenset(self.active_since())
