from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus


class CandidateMeaningRepository(ABC):
    """Port for the meaning enrichment of a candidate.

    1:1 with candidates. `None` from get methods means no row exists for this
    candidate (i.e., generation has never been attempted).
    """

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMeaning | None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMeaning]:
        """Return a mapping {candidate_id: CandidateMeaning} for all rows belonging
        to candidates of the given source. Used to bulk-load enrichments when
        listing candidates."""

    @abstractmethod
    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMeaning]:
        """Return a mapping for the explicit list of candidate ids."""

    @abstractmethod
    def upsert(self, meaning: CandidateMeaning) -> None:
        """Insert or update the meaning row for the contained candidate_id."""

    @abstractmethod
    def get_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
        sort_order: CandidateSortOrder | None = None,
    ) -> list[int]:
        """Return ids of candidates that have no meaning row OR meaning row with
        meaning IS NULL. If only_active=True, restrict to candidates with
        status PENDING or LEARN. sort_order controls ordering (default RELEVANCE)."""

    @abstractmethod
    def count_candidate_ids_without_meaning(
        self,
        source_id: int | None,
        only_active: bool,
    ) -> int: ...

    @abstractmethod
    def mark_queued_bulk(self, candidate_ids: list[int]) -> None:
        """Upsert status=QUEUED for each candidate. Preserves existing meaning/ipa
        on retry of failed rows (only flips status + clears error).

        If a row doesn't exist yet, creates a placeholder row with NULL meaning/ipa."""

    @abstractmethod
    def mark_running(self, candidate_id: int) -> None:
        """Set status=RUNNING on existing row. No-op if no row exists."""

    @abstractmethod
    def mark_failed(self, candidate_id: int, error: str) -> None:
        """Set status=FAILED and error text. No-op if no row exists."""

    @abstractmethod
    def mark_batch_failed(self, candidate_ids: list[int], error: str) -> None:
        """Bulk FAILED for a whole batch (used by worker on_job_end)."""

    @abstractmethod
    def get_candidate_ids_by_status(
        self, source_id: int, status: EnrichmentStatus,
    ) -> list[int]:
        """Return candidate ids from the given source whose meaning row has the given status.
        Used by cancel/retry-failed endpoints."""
