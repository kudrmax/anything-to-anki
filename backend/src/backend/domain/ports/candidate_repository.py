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
    def get_by_source(self, source_id: int) -> list[StoredCandidate]: ...

    @abstractmethod
    def get_by_id(self, candidate_id: int) -> StoredCandidate | None: ...

    @abstractmethod
    def update_status(self, candidate_id: int, status: CandidateStatus) -> None: ...

    @abstractmethod
    def count_by_status(self, status: CandidateStatus) -> int: ...

    @abstractmethod
    def update_meaning(self, candidate_id: int, meaning: str) -> None: ...

    @abstractmethod
    def update_meaning_and_ipa(self, candidate_id: int, meaning: str, ipa: str | None) -> None: ...

    @abstractmethod
    def update_context_fragment(self, candidate_id: int, context_fragment: str) -> None: ...

    @abstractmethod
    def get_without_meaning(self, source_id: int | None, limit: int) -> list[StoredCandidate]:
        """Get candidates without meaning, ordered by sweet_spot DESC, cefr_level DESC."""

    @abstractmethod
    def count_without_meaning(self, source_id: int | None) -> int:
        """Count candidates that don't have a meaning yet."""

    @abstractmethod
    def get_active_without_meaning(self, source_id: int | None, limit: int) -> list[StoredCandidate]:
        """Get candidates with status PENDING or LEARN that have no meaning yet,
        ordered by sweet_spot DESC, cefr_level DESC."""

    @abstractmethod
    def count_active_without_meaning(self, source_id: int | None) -> int:
        """Count candidates with status PENDING or LEARN that have no meaning yet."""

    @abstractmethod
    def get_by_ids(self, candidate_ids: list[int]) -> list[StoredCandidate]:
        """Get candidates by explicit list of IDs, preserving order."""

    @abstractmethod
    def get_all_active_without_meaning(self, source_id: int | None) -> list[StoredCandidate]:
        """Get ALL candidates with status PENDING or LEARN that have no meaning (no limit),
        ordered by sweet_spot DESC, cefr_level DESC."""

    @abstractmethod
    def delete_by_source(self, source_id: int) -> None: ...
