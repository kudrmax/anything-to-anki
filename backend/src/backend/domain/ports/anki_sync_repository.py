from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from backend.domain.services.decision_rules import BindingRef
    from backend.domain.value_objects.anki_binding import AnkiBinding


class AnkiSyncRepository(ABC):
    """Port for the bindings of cards to Anki notes. A binding is never deleted: release
    keeps it as history."""

    @abstractmethod
    def bind(self, binding: AnkiBinding) -> None:
        """A new active binding; released ones of the same note stay."""

    @abstractmethod
    def release(self, phrase_ids: Iterable[int], at: datetime) -> None:
        """Release the active binding of each card."""

    @abstractmethod
    def release_rows(self, binding_ids: Iterable[int], at: datetime) -> None:
        """Release active bindings by their own id: those whose card is gone."""

    @abstractmethod
    def orphans(self, lemma: str) -> list[BindingRef]:
        """Active bindings of the lemma whose card or source is gone."""
