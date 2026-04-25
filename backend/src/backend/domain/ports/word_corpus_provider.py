from __future__ import annotations

from abc import ABC, abstractmethod


class WordCorpusProvider(ABC):
    """Port for accessing the word corpus (all known lemma+POS pairs from dictionaries)."""

    @abstractmethod
    def get_all_lemma_pos_pairs(self) -> list[tuple[str, str]]: ...
