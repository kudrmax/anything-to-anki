from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.candidate_media import CandidateMedia


class CandidateMediaRepository(ABC):
    """Port for the media enrichment (screenshot + audio + timecodes) of a candidate.

    1:1 with candidates. `None` from get methods means no row exists for this
    candidate (extraction has never been attempted)."""

    @abstractmethod
    def get_by_candidate_id(self, candidate_id: int) -> CandidateMedia | None: ...

    @abstractmethod
    def get_all_by_source(self, source_id: int) -> dict[int, CandidateMedia]: ...

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
