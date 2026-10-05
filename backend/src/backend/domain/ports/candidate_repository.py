from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.candidate_status import CandidateStatus


class CandidateRepository(ABC):
    """Port for persisting and retrieving word candidates."""

    @abstractmethod
    def create_batch(self, candidates: list[StoredCandidate]) -> list[StoredCandidate]: ...

    @abstractmethod
    def get_by_source(self, source_id: int) -> list[StoredCandidate]:
        """Return candidates for the source, unsorted."""

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> StoredCandidate | None: ...

    @abstractmethod
    def update_status(self, candidate_id: int, status: CandidateStatus) -> None: ...

    @abstractmethod
    def count_by_status(self, status: CandidateStatus) -> int: ...

    @abstractmethod
    def count_all(self) -> int: ...

    @abstractmethod
    def update_context_fragment(self, candidate_id: int, context_fragment: str) -> None:
        """Set a new source phrase. Its polished version no longer applies and is dropped."""

    @abstractmethod
    def set_polished_fragment(self, candidate_id: int, polished_fragment: str | None) -> None:
        """Store AI's easier version of the phrase; None drops it. Clears a revert."""

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
