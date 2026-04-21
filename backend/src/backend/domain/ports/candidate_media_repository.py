from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.value_objects.enrichment_status import EnrichmentStatus
    from backend.domain.value_objects.failed_error_group import FailedErrorGroup


class CandidateMediaRepository(ABC):
    """Port for the media enrichment (screenshot + audio + timecodes) of a candidate.

    1:1 with candidates. `None` from get methods means no row exists for this
    candidate (extraction has never been attempted)."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]: ...

    @abstractmethod
    def get_all_by_source_id(self, source_id: int) -> list[CandidateMedia]: ...

    @abstractmethod
    def get_by_candidate_ids(self, candidate_ids: list[int]) -> dict[int, CandidateMedia]: ...

    @abstractmethod
    def upsert(self, media: CandidateMedia) -> None:
        """Insert or update the media row for the contained candidate_id."""

    @abstractmethod
    def clear_paths(
        self,
        candidate_id: int,
        *,
        clear_screenshot: bool,
        clear_audio: bool,
    ) -> None:
        """Set screenshot_path and/or audio_path to NULL on the existing row.

        Used by CleanupMediaUseCase when the user purges files but keeps the row
        (so timecodes are not lost)."""

    @abstractmethod
    def get_eligible_candidate_ids(
        self,
        source_id: int,
    ) -> list[int]:
        """Return ids of candidates of `source_id` that:
        - have status PENDING or LEARN
        - have a candidate_media row with start_ms / end_ms set
        - have NULL screenshot_path on that row (= media not yet generated)

        Returned unsorted. Used by enqueue media generation use case."""

    @abstractmethod
    def mark_queued_bulk(self, candidate_ids: list[int]) -> None:
        """Upsert status=QUEUED for each candidate. Preserves existing timecodes/paths
        on retry of failed rows (only flips status + clears error).

        If a row doesn't exist yet, creates a placeholder row with all None fields."""

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
    def mark_batch_cancelled(self, candidate_ids: list[int]) -> None:
        """Bulk CANCELLED for a whole batch (used by cancel endpoint)."""

    @abstractmethod
    def fail_all_running(self, error: str) -> int:
        """Mark all RUNNING rows as FAILED with the given error.

        Used by worker startup reconciliation to clean up zombie rows
        left after a crash. Returns count of affected rows."""

    @abstractmethod
    def get_candidate_ids_by_status(
        self, source_id: int, status: EnrichmentStatus,
    ) -> list[int]:
        """Return candidate ids from the given source whose media row has the given status.
        Used by cancel/retry-failed endpoints."""

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
