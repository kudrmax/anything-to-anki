from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.dictionary_entry import DictionaryEntry


class DictionaryProvider(ABC):
    """Port for fetching word definitions and IPA transcriptions."""

    @abstractmethod
    def get_entry(self, lemma: str, pos: str) -> DictionaryEntry:
        """Return a dictionary entry for the given lemma and POS tag."""
