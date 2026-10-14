from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.word_status import WordStatus


class CandidateRepository(ABC):
    """Port for the words of sources. Their phrases go through the occurrence repository."""

    @abstractmethod
    def add_word(self, word: StoredCandidate) -> int:
        """Store a new word without phrases; returns its id. Its phrases go through the
        occurrence repository."""

    @abstractmethod
    def set_word_status(
        self,
        candidate_id: int,
        status: WordStatus,
        *,
        known_added: bool = False,
        was_unknown: bool = False,
    ) -> None:
        """The decision on the word; the phrase of the decision is the phrases' business.
        `known_added`: a Known decision that put the lemma into the user's Known;
        `was_unknown`: the user had marked it unknown before that."""

    @abstractmethod
    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        """Return candidates for the source, unsorted."""

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> StoredCandidate | None: ...

    @abstractmethod
    def count_by_status(self, status: WordStatus) -> int:
        """Words with this decision, across all sources."""

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
    def get_all_by_status(self, status: WordStatus) -> list[StoredCandidate]:
        """Words with this decision across all sources, by source."""

    @abstractmethod
    def get_by_lemma(self, lemma: str) -> list[StoredCandidate]:
        """Return candidates with the given lemma across all sources."""
