from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.entities.candidate_media import CandidateMedia


class CandidateMediaRepository(ABC):
    """Port for the media enrichment (screenshot + audio + timecodes) of a candidate.

    1:1 with candidates. `None` from get methods means no row exists for this
    candidate (extraction has never been attempted)."""

    # ── by phrase ──────────────────────────────────────────────────────

    @abstractmethod
    def get_by_phrase_id(self, phrase_id: int) -> CandidateMedia | None: ...

    @abstractmethod
    def get_by_phrase_ids(self, phrase_ids: list[int]) -> dict[int, CandidateMedia]:
        """Keyed by phrase id; phrases without a row are left out."""

    @abstractmethod
    def upsert_for_phrase(self, phrase_id: int, media: CandidateMedia) -> None: ...

    @abstractmethod
    def clear_phrase_paths(
        self, phrase_id: int, *, clear_screenshot: bool, clear_audio: bool,
    ) -> None:
        """Set the phrase's screenshot_path and/or audio_path to NULL, keeping the row."""

    @abstractmethod
    def set_timecodes(self, times: Mapping[int, tuple[int, int] | None]) -> None:
        """Phrase id → the time of its phrase in the video, None when untimed.

        A phrase whose screenshot or clip is made keeps its media as it is: the files were
        cut at those times. No row is made for an untimed phrase."""

    # ── by word, through its primary phrase ────────────────────────────
    # TRANSITIONAL(words-phrases): removed in Task 10

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
