from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection
    from datetime import datetime

    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.built_analysis import WordKey


class CandidateRepository(ABC):
    """Port for the words of sources. Their phrases go through the occurrence repository."""

    @abstractmethod
    def add_word(self, word: StoredCandidate) -> int:
        """Store a new word without phrases; returns its id. Its phrases go through the
        occurrence repository."""

    @abstractmethod
    def word_id(self, source_id: int, key: WordKey) -> int | None:
        """The word of the source with this key, if the source has it."""

    @abstractmethod
    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        """Return candidates for the source, unsorted."""

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> StoredCandidate | None: ...

    @abstractmethod
    def count_learning_in_anki(self) -> int:
        """Words learning in Anki (`card_view.learning_in_anki`), across all sources."""

    @abstractmethod
    def count_all(self) -> int: ...

    @abstractmethod
    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        """Get candidates by explicit list of IDs, preserving order."""

    @abstractmethod
    def get_lemma_map(self, candidate_ids: list[int]) -> dict[int, str]:
        """Return {candidate_id: lemma} for the given ids; missing ids are omitted."""

    @abstractmethod
    def delete_by_source(self, source_id: int) -> None: ...

    @abstractmethod
    def chosen_to_learn(self, source_ids: Collection[int] | None = None) -> list[StoredCandidate]:
        """Words chosen to learn (`card_view.chosen_to_learn`) of these sources, or of all
        sources, by id; read from their decision cards, not the projection."""

    @abstractmethod
    def get_by_lemma(self, lemma: str) -> list[StoredCandidate]:
        """Return candidates with the given lemma across all sources."""

    @abstractmethod
    def set_studied_at(self, word_id: int, studied_at: datetime | None) -> None:
        """When a card of the word was last marked; None once no card of it is."""

    @abstractmethod
    def last_studied(self, source_ids: Collection[int]) -> dict[int, datetime]:
        """The latest mark on a card of each source; sources never marked are omitted."""
