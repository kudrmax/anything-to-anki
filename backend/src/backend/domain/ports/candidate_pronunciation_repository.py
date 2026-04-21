from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    from backend.domain.value_objects.failed_error_group import FailedErrorGroup


class CandidatePronunciationRepository(ABC):
    """Port for persisting pronunciation enrichment data."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidatePronunciation | None: ...

    @abstractmethod
    def get_by_candidate_ids(
        self, candidate_ids: list[int],
    ) -> dict[int, CandidatePronunciation]: ...

    @abstractmethod
    def upsert(self, pronunciation: CandidatePronunciation) -> None: ...

    @abstractmethod
    def get_eligible_candidate_ids(self, source_id: int) -> list[int]: ...

    @abstractmethod
    def mark_queued_bulk(self, candidate_ids: list[int]) -> None: ...

    @abstractmethod
    def mark_running(self, candidate_id: int) -> None: ...

    @abstractmethod
    def mark_failed(self, candidate_id: int, error: str) -> None: ...

    @abstractmethod
    def mark_batch_cancelled(self, candidate_ids: list[int]) -> None: ...

    @abstractmethod
    def fail_all_running(self, error: str) -> int: ...

    @abstractmethod
    def get_candidate_ids_by_status(
        self, source_id: int, status: EnrichmentStatus,
    ) -> list[int]: ...

    @abstractmethod
    def count_by_status_global(
        self,
        status: EnrichmentStatus,
        source_id: int | None = None,
    ) -> int:
        """Count enrichments with given status across all sources (or one source)."""

    @abstractmethod
    def get_failed_grouped_by_error(
        self,
        source_id: int | None = None,
    ) -> list[FailedErrorGroup]:
        """Return failed enrichments grouped by error text.

        Each group includes per-source breakdown and candidate_ids for retry.
        """

    @abstractmethod
    def get_candidate_ids_by_error(
        self,
        error_text: str,
        source_id: int | None = None,
    ) -> list[int]:
        """Return candidate IDs with a specific error text, for targeted retry."""

    @abstractmethod
    def get_source_ids_by_enrichment_status(
        self,
        status: EnrichmentStatus,
    ) -> list[int]:
        """Return distinct source IDs that have at least one enrichment with given status."""
