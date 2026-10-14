from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.candidate_status import CandidateStatus
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.phrase_origin import PhraseOrigin
    from backend.domain.value_objects.word_status import WordStatus


class CandidateRepository(ABC):
    """Port for persisting and retrieving word candidates."""

    @abstractmethod
    def create_batch(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]: ...

    @abstractmethod
    def add_word(self, word: StoredCandidate) -> int:
        """Store a new word without phrases; returns its id. Its phrases go through the
        occurrence repository."""

    @abstractmethod
    def set_word_status(
        self, candidate_id: int, status: WordStatus, *, known_added: bool = False,
    ) -> None:
        """The decision on the word; the phrase of the decision is the phrases' business.
        `known_added`: a Known decision that put the lemma into the user's Known."""

    @abstractmethod
    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        """Return candidates for the source, unsorted."""

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> StoredCandidate | None: ...

    @abstractmethod
    def set_origin(self, candidate_id: int, origin: PhraseOrigin | None) -> None:
        """Where the word's collected phrase came from."""

    @abstractmethod
    def count_by_status(self, status: CandidateStatus) -> int: ...

    @abstractmethod
    def count_all(self) -> int: ...

    @abstractmethod
    def set_polished_phrase(self, candidate_id: int, phrase: Phrase | None) -> None:
        """Store the rewritten phrase; None drops it. Clears a revert."""

    @abstractmethod
    def set_polish_reverted(self, candidate_id: int, reverted: bool) -> None: ...

    @abstractmethod
    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        """Get candidates by explicit list of IDs, preserving order."""

    @abstractmethod
    def get_lemma_map(self, candidate_ids: list[int]) -> dict[int, str]:
        """Return {candidate_id: lemma} for the given ids; missing ids are omitted."""

    @abstractmethod
    def delete_by_source(self, source_id: int) -> None: ...

    @abstractmethod
    def get_all_by_status(self, status: CandidateStatus) -> list[StoredCandidate]:
        """Return all candidates with the given status, across all sources."""

    @abstractmethod
    def get_by_lemma(self, lemma: str) -> list[StoredCandidate]:
        """Return candidates with the given lemma across all sources."""
